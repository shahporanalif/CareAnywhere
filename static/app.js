const $ = id => document.getElementById(id);
const { t, setLanguage, getLanguage, applyTranslations } = window.CareAnywhereI18n;

document.addEventListener('click', event => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target?.closest('#languageToggle')) return;

  setLanguage(getLanguage() === 'en' ? 'bn' : 'en');
  try {
    refreshLanguageDependentUI();
  } catch (error) {
    console.error('Could not refresh translated dynamic content:', error);
  }
});

const themeToggle = $('themeToggle');
function setTheme(theme) {
  const dark = theme === 'dark';
  document.body.dataset.theme = dark ? 'dark' : 'light';
  themeToggle.querySelector('.theme-icon').textContent = dark ? '☀' : '☾';
  themeToggle.setAttribute('aria-label', t(dark ? 'theme.switchLight' : 'theme.switchDark'));
  themeToggle.title = t(dark ? 'theme.switchLight' : 'theme.switchDark');
  document.querySelector('meta[name="theme-color"]').content = dark ? '#0D0D0D' : '#f7f8fa';
}

let savedTheme = null;
try { savedTheme = localStorage.getItem('careanywhere-theme'); } catch {}
setTheme(savedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
themeToggle.addEventListener('click', () => {
  const next = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(next);
  try { localStorage.setItem('careanywhere-theme', next); } catch {}
});

let history = [];
let imageData = null;
let recorder = null;
let audioChunks = [];
let cameraStream = null;
let lastAnswer = '';
let chatGeneration = 0;
let requestController = null;
let discardRecording = false;
let connectionState = 'checking';
let finderMessageState = { key: 'finder.initialMessage', values: {} };
let finderMapUnavailable = false;
let finderUnavailable = false;

function formatNumber(value, options = {}) {
  return new Intl.NumberFormat(getLanguage() === 'bn' ? 'bn-BD' : 'en-US', options).format(value);
}

function formatLocalDate(value) {
  if (!value) return getLanguage() === 'bn' ? 'তারিখ অজানা' : 'unknown date';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : new Intl.DateTimeFormat(getLanguage() === 'bn' ? 'bn-BD' : 'en-US', { dateStyle: 'medium' }).format(date);
}

const knownApiErrors = new Map([
  ['Invalid API token', 'errors.invalidToken'],
  ['Set OPENAI_API_KEY and PINECONE_API_KEY in .env', 'errors.configureKeys'],
  ['AI service failed. Check server logs, credentials, Pinecone index, and connectivity.', 'errors.aiService'],
  ['Speech transcription unavailable', 'errors.transcriptionUnavailable'],
  ['Speech synthesis unavailable', 'errors.speechSynthesisUnavailable'],
  ['Nearby search timed out on all available map data services. Try again later or choose a smaller radius.', 'errors.healthcareTimeout'],
  ['Nearby healthcare data is temporarily unavailable because all map data providers timed out. Try again later.', 'errors.healthcareTimeout'],
  ['Map data services are busy. Please wait and try again.', 'errors.healthcareBusy'],
  ['Nearby healthcare search is temporarily unavailable. Please try again later.', 'errors.healthcareUnavailable'],
  ['Could not reach an available map data service. Please try again later.', 'errors.healthcareReach'],
  ['The map data service rejected the nearby search query.', 'errors.healthcareQuery'],
  ['Nearby searches are busy. Please wait a minute and try again.', 'errors.healthcareRateMinute'],
  ['Nearby search daily limit reached. Please try again later.', 'errors.healthcareRateDay']
]);

function translatedError(message, fallbackKey = 'errors.requestFailed') {
  const key = knownApiErrors.get(message);
  if (key) return t(key);
  return message || t(fallbackKey);
}

function renderConnectionStatus() {
  const status = $('status');
  const labels = {
    checking: ['status.checking', 'status.checking'],
    connected: ['status.connected', 'status.connectedTitle'],
    setup: ['status.setupNeeded', 'status.setupTitle'],
    offline: ['status.offline', 'status.offlineTitle']
  };
  const [labelKey, titleKey] = labels[connectionState];
  status.querySelector('span').textContent = t(labelKey);
  status.title = t(titleKey);
}

function renderFinderMessage() {
  const { key, values, raw } = finderMessageState;
  const message = raw ? translatedError(raw, key) : t(key, values);
  $('finderMessage').textContent = finderMapUnavailable ? `${message}${t('finder.mapUnavailable')}` : message;
}

function renderHealthcareFailure() {
  $('resultCount').textContent = t('finder.unavailableCount');
  $('facilityList').replaceChildren();
  const unavailable = document.createElement('li');
  unavailable.className = 'empty-results';
  unavailable.textContent = t('finder.resultsUnavailable');
  $('facilityList').appendChild(unavailable);
}

function refreshLanguageDependentUI() {
  applyTranslations();
  renderConnectionStatus();
  renderFinderMessage();
  resizeMessage();
  const micLabel = $('mic').querySelector('[data-i18n]');
  if (micLabel) applyTranslations($('mic'));
  if ($('send').disabled) $('send').setAttribute('aria-label', t('chat.sending'));
  else $('send').setAttribute('aria-label', t('chat.send'));
  setTheme(document.body.dataset.theme || 'light');
  document.querySelectorAll('.chat-error').forEach(node => {
    node.textContent = t('chat.error', { detail: translatedError(node.dataset.errorDetail, 'errors.chatNetwork') });
  });
  document.querySelectorAll('.source-note[data-source-page]').forEach(node => {
    node.textContent = t('sources.knowledgeBase', { page: node.dataset.sourcePage });
  });
  if (finderUnavailable) renderHealthcareFailure();
  else if (currentCoordinates || nearbyFacilities.length) renderHealthcareResults();
}

const headers = () => {
  const result = {};
  const token = $('token').value.trim();
  if (token) result.Authorization = `Bearer ${token}`;
  return result;
};

function appendSources(parent, sources) {
  if (!sources?.length) return;

  const list = document.createElement('div');
  list.className = 'sources';

  const heading = document.createElement('span');
  heading.className = 'sources-title';
  heading.dataset.i18n = 'sources.title';
  heading.textContent = t('sources.title');
  list.appendChild(heading);

  sources.slice(0, 8).forEach(source => {
    const item = document.createElement('span');
    item.className = 'source-note';

    if (source.type === 'pdf') {
      item.dataset.sourcePage = source.page;
      item.textContent = t('sources.knowledgeBase', { page: source.page });
    } else if (source.url) {
      let safeUrl = null;
      try {
        const parsed = new URL(source.url);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') safeUrl = parsed.href;
      } catch {}

      if (safeUrl) {
        const link = document.createElement('a');
        link.href = safeUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = source.title || new URL(safeUrl).hostname;
        item.appendChild(link);
      } else {
        item.textContent = source.title || t('sources.web');
      }
    }

    if (item.textContent || item.childElementCount) list.appendChild(item);
  });

  parent.appendChild(list);
}

function bubble(text, kind = 'bot', sources = []) {
  const row = document.createElement('div');
  row.className = `message-row ${kind}-row`;

  const message = document.createElement('article');
  message.className = kind;
  message.textContent = text;
  appendSources(message, sources);

  row.appendChild(message);
  $('messages').appendChild(row);
  $('messages').scrollTop = $('messages').scrollHeight;
  return message;
}

async function check() {
  const status = $('status');
  status.classList.remove('connected', 'offline');
  try {
    const response = await fetch('/api/health');
    const data = await response.json();
    if (!response.ok) throw new Error('Health check failed');

    connectionState = data.configured ? 'connected' : 'setup';
    status.classList.add(data.configured ? 'connected' : 'offline');
  } catch {
    connectionState = 'offline';
    status.classList.add('offline');
  }
  renderConnectionStatus();
}
check();

function resizeMessage() {
  const input = $('message');
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  $('charCount').textContent = `${formatNumber(input.value.length)} / ${formatNumber(4000)}`;
}

$('message').addEventListener('input', resizeMessage);
$('message').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $('chatForm').requestSubmit();
  }
});

document.querySelectorAll('.suggestion').forEach(button => {
  button.addEventListener('click', () => {
    $('message').value = button.textContent.trim();
    resizeMessage();
    $('message').focus();
  });
});

function setImage(file) {
  if (!file) return;
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 5e6) {
    alert(t('image.invalidType'));
    $('image').value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    imageData = reader.result;
    $('thumbnail').src = imageData;
    $('preview').hidden = false;
  };
  reader.onerror = () => alert(t('image.readError'));
  reader.readAsDataURL(file);
}

$('image').addEventListener('change', event => setImage(event.target.files[0]));
$('image').previousElementSibling.addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    $('image').click();
  }
});
$('remove').addEventListener('click', () => {
  imageData = null;
  $('thumbnail').removeAttribute('src');
  $('preview').hidden = true;
  $('image').value = '';
});

$('chatForm').addEventListener('submit', async event => {
  event.preventDefault();
  const message = $('message').value.trim();
  if (!message) return;

  $('welcome').hidden = true;
  const prior = history.slice(-8);
  const generation = chatGeneration;
  const controller = new AbortController();
  requestController = controller;
  bubble(message, 'user');
  $('message').value = '';
  resizeMessage();
  $('send').disabled = true;
  $('send').setAttribute('aria-label', t('chat.sending'));

  const pending = bubble('', 'bot');
  pending.classList.add('typing');
  const label = document.createElement('span');
  label.dataset.i18n = 'chat.thinking';
  label.textContent = t('chat.thinking');
  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  for (let index = 0; index < 3; index += 1) dots.appendChild(document.createElement('i'));
  pending.append(label, dots);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { ...headers(), 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({ message, history: prior, image_data: imageData })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed');
    if (generation !== chatGeneration) return;

    pending.classList.remove('typing');
    pending.replaceChildren(document.createTextNode(data.answer));
    appendSources(pending, data.sources);
    lastAnswer = data.answer;
    history.push(
      { role: 'user', content: message },
      { role: 'assistant', content: data.answer }
    );
    if (imageData) $('remove').click();
  } catch (error) {
    if (error.name !== 'AbortError' && generation === chatGeneration) {
      pending.classList.remove('typing');
      pending.classList.add('chat-error');
      pending.dataset.errorDetail = error.message;
      pending.textContent = t('chat.error', { detail: translatedError(error.message, 'errors.chatNetwork') });
    }
  } finally {
    if (generation !== chatGeneration) return;
    requestController = null;
    $('send').disabled = false;
    $('send').setAttribute('aria-label', t('chat.send'));
    $('message').focus();
    $('messages').scrollTop = $('messages').scrollHeight;
  }
});

$('mic').addEventListener('click', async () => {
  if (recorder?.state === 'recording') {
    recorder.stop();
    $('mic').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3m-4 0h8"/></svg><span data-i18n="tools.voice">Voice</span>';
    $('mic').classList.remove('recording');
    $('mic').setAttribute('aria-pressed', 'false');
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const generation = chatGeneration;
    audioChunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = event => audioChunks.push(event.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop());
      if (discardRecording) {
        discardRecording = false;
        return;
      }
      const blob = new Blob(audioChunks, { type: recorder.mimeType });
      const formData = new FormData();
      formData.append('file', blob, 'voice.webm');
      $('mic').disabled = true;
      try {
        const response = await fetch('/api/transcribe', { method: 'POST', headers: headers(), body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || t('errors.transcriptionFailed'));
        if (generation !== chatGeneration) return;
        $('message').value = data.text;
        resizeMessage();
        $('message').focus();
      } catch (error) {
        alert(translatedError(error.message, 'errors.transcriptionFailed'));
      } finally {
        $('mic').disabled = false;
      }
    };
    recorder.start();
    $('mic').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg><span data-i18n="tools.stop">Stop</span>';
    $('mic').classList.add('recording');
    $('mic').setAttribute('aria-pressed', 'true');
  } catch (error) {
    alert(t('errors.microphoneUnavailable', { detail: translatedError(error.message) }));
  }
});

$('listen').addEventListener('click', async () => {
  if (!lastAnswer) return alert(t('errors.askFirst'));
  $('listen').disabled = true;
  let audioUrl;
  try {
    const response = await fetch('/api/speak', {
      method: 'POST',
      headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: lastAnswer })
    });
    if (!response.ok) throw new Error(t('errors.speechUnavailable'));
    audioUrl = URL.createObjectURL(await response.blob());
    const audio = new Audio(audioUrl);
    audio.onended = () => URL.revokeObjectURL(audioUrl);
    audio.onerror = () => URL.revokeObjectURL(audioUrl);
    await audio.play();
  } catch (error) {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    alert(translatedError(error.message, 'errors.speechUnavailable'));
  } finally {
    $('listen').disabled = false;
  }
});

$('camera').addEventListener('click', async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    $('video').srcObject = cameraStream;
    $('video').hidden = false;
    $('cameraActions').hidden = false;
    await $('video').play();
  } catch (error) {
    alert(t('errors.cameraUnavailable', { detail: translatedError(error.message) }));
    cameraStream?.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
});

function closeCamera() {
  cameraStream?.getTracks().forEach(track => track.stop());
  cameraStream = null;
  $('video').srcObject = null;
  $('video').hidden = true;
  $('cameraActions').hidden = true;
}
$('closeCamera').addEventListener('click', closeCamera);

$('snap').addEventListener('click', () => {
  const video = $('video');
  const canvas = $('canvas');
  if (!video.videoWidth || !video.videoHeight) return alert(t('camera.notReady'));
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob(blob => {
    if (blob) setImage(new File([blob], 'camera.jpg', { type: 'image/jpeg' }));
  }, 'image/jpeg', .85);
  closeCamera();
});

$('newChat').addEventListener('click', () => {
  chatGeneration += 1;
  requestController?.abort();
  requestController = null;
  $('send').disabled = false;
  history = [];
  lastAnswer = '';
  $('message').value = '';
  resizeMessage();
  $('remove').click();
  if (recorder?.state === 'recording') {
    discardRecording = true;
    recorder.stop();
  }
  $('mic').classList.remove('recording');
  $('mic').setAttribute('aria-pressed', 'false');
  $('mic').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3m-4 0h8"/></svg><span data-i18n="tools.voice">Voice</span>';
  applyTranslations($('mic'));
  closeCamera();
  $('messages').replaceChildren($('welcome'));
  $('messages').scrollTop = 0;
  $('welcome').hidden = false;
  $('message').focus();
});

// Nearby healthcare finder. The coordinates stay in this page and the finder
// request; they are never added to the medical chat payload.
let healthcareMap = null;
let facilityLayer = null;
let userLocationMarker = null;
let radiusCircle = null;
let currentCoordinates = null;
let nearbyFacilities = [];
let selectedCategory = 'all';
let searchGeneration = 0;
let searchController = null;
let activeSearchKey = null;
let radiusSearchTimer = null;
const inFlightHealthcareSearches = new Map();
const recentHealthcareSearches = new Map();
const FRONTEND_RESULT_CACHE_MS = 30_000;

const categoryNames = {
  hospital: 'category.hospital',
  clinic: 'category.clinic',
  pharmacy: 'category.pharmacy',
  doctors: 'category.doctorLabel'
};
const categorySymbols = { hospital: 'H', clinic: 'C', pharmacy: 'P', doctors: 'D' };

function setFinderMessage(key, values = {}, raw = null) {
  finderMessageState = { key, values, raw };
  renderFinderMessage();
}

function categoryLabel(category) {
  return t(categoryNames[category] || 'category.unknown');
}

function ensureHealthcareMap() {
  if (healthcareMap) return true;
  if (!window.L) return false;

  healthcareMap = L.map('map', { scrollWheelZoom: false, preferCanvas: true });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(healthcareMap);
  facilityLayer = L.layerGroup().addTo(healthcareMap);
  return true;
}

function formatDistance(meters) {
  return meters < 1000
    ? `${formatNumber(meters)} ${getLanguage() === 'bn' ? 'মি' : 'm'}`
    : `${formatNumber(meters / 1000, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${getLanguage() === 'bn' ? 'কিমি' : 'km'}`;
}

function markerPopup(facility) {
  const popup = document.createElement('div');
  const name = document.createElement('strong');
  name.textContent = facility.name;
  const type = document.createElement('div');
  type.textContent = categoryLabel(facility.category);
  const distance = document.createElement('div');
  distance.textContent = formatDistance(facility.distance_m);
  popup.append(name, type, distance);
  if (facility.address) {
    const address = document.createElement('div');
    address.textContent = facility.address;
    popup.appendChild(address);
  }
  return popup;
}

function safeDirectionsUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && url.hostname === 'www.openstreetmap.org') return url.href;
  } catch {}
  return null;
}

function directionsUrlFor(facility) {
  if (!currentCoordinates) return null;
  const url = new URL('https://www.openstreetmap.org/directions');
  url.searchParams.set('engine', 'fossgis_osrm_car');
  url.searchParams.set(
    'route',
    `${currentCoordinates.lat.toFixed(6)},${currentCoordinates.lon.toFixed(6)};${facility.lat.toFixed(6)},${facility.lon.toFixed(6)}`
  );
  return safeDirectionsUrl(url.href);
}

function renderHealthcareResults() {
  const visible = selectedCategory === 'all'
    ? nearbyFacilities
    : nearbyFacilities.filter(facility => facility.category === selectedCategory);

  $('resultCount').textContent = t(visible.length === 1 ? 'finder.placeCount.one' : 'finder.placeCount.other', { count: formatNumber(visible.length) });
  $('facilityList').replaceChildren();
  facilityLayer?.clearLayers();

  visible.forEach(facility => {
    if (healthcareMap && facilityLayer) {
      const icon = L.divIcon({
        className: `health-marker ${facility.category}`,
        html: `<span aria-hidden="true">${categorySymbols[facility.category] || 'H'}</span>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
      const marker = L.marker([facility.lat, facility.lon], { icon })
        .bindPopup(markerPopup(facility))
        .addTo(facilityLayer);
      facility._marker = marker;
    }

    const item = document.createElement('li');
    item.className = 'facility-card';
    const top = document.createElement('div');
    top.className = 'facility-card-top';
    const symbol = document.createElement('span');
    symbol.className = `facility-symbol ${facility.category}`;
    symbol.setAttribute('aria-hidden', 'true');
    symbol.textContent = categorySymbols[facility.category] || 'H';
    const info = document.createElement('div');
    info.className = 'facility-info';
    const name = document.createElement('button');
    name.className = 'facility-name-button';
    name.type = 'button';
    name.textContent = facility.name;
    name.setAttribute('aria-label', t('finder.showOnMap', { name: facility.name }));
    name.addEventListener('click', () => {
      if (!healthcareMap) return;
      healthcareMap.setView([facility.lat, facility.lon], Math.max(healthcareMap.getZoom(), 16));
      facility._marker?.openPopup();
    });
    const type = document.createElement('span');
    type.className = 'facility-type';
    type.textContent = categoryLabel(facility.category);
    info.append(name, type);
    top.append(symbol, info);
    item.appendChild(top);

    if (facility.address) {
      const address = document.createElement('p');
      address.className = 'facility-address';
      address.textContent = facility.address;
      item.appendChild(address);
    }

    const bottom = document.createElement('div');
    bottom.className = 'facility-card-bottom';
    const distance = document.createElement('span');
    distance.className = 'facility-distance';
    distance.textContent = formatDistance(facility.distance_m);
    bottom.appendChild(distance);
    const directionsUrl = directionsUrlFor(facility);
    if (directionsUrl) {
      const directions = document.createElement('a');
      directions.className = 'directions-link';
      directions.href = directionsUrl;
      directions.target = '_blank';
      directions.rel = 'noopener noreferrer';
      directions.textContent = t('finder.directions');
      bottom.appendChild(directions);
    }
    item.appendChild(bottom);
    $('facilityList').appendChild(item);
  });

  if (nearbyFacilities.length && !visible.length) {
    const empty = document.createElement('li');
    empty.className = 'empty-results';
    empty.textContent = t('finder.noCategoryPlaces');
    $('facilityList').appendChild(empty);
  } else if (!nearbyFacilities.length) {
    const empty = document.createElement('li');
    empty.className = 'empty-results';
    empty.textContent = t('finder.noPlaces');
    $('facilityList').appendChild(empty);
  }

  if (healthcareMap) healthcareMap.invalidateSize();
}

function shareHealthcareSearch(searchKey, startRequest) {
  const existing = inFlightHealthcareSearches.get(searchKey);
  if (existing) return existing;
  const request = Promise.resolve().then(startRequest);
  inFlightHealthcareSearches.set(searchKey, request);
  const clearRequest = () => {
    if (inFlightHealthcareSearches.get(searchKey) === request) inFlightHealthcareSearches.delete(searchKey);
  };
  request.then(clearRequest, clearRequest);
  return request;
}

function searchHealthcare(lat, lon) {
  if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
    setFinderMessage('finder.invalidCoordinates');
    return Promise.resolve();
  }

  const radius = Number($('searchRadius').value);
  const category = 'all'; // The category chips filter this complete result locally.
  const searchKey = `${lat.toFixed(5)},${lon.toFixed(5)},${radius},${category}`;
  if (radiusSearchTimer) clearTimeout(radiusSearchTimer);
  return shareHealthcareSearch(searchKey, () => performHealthcareSearch(lat, lon, radius, category, searchKey));
}

async function performHealthcareSearch(lat, lon, radius, category, searchKey) {
  currentCoordinates = { lat, lon };
  searchGeneration += 1;
  const generation = searchGeneration;
  searchController?.abort();
  const controller = new AbortController();
  searchController = controller;
  activeSearchKey = searchKey;
  const searchButton = $('searchNearMe');
  const manualButton = $('manualSearch').querySelector('button[type="submit"]');
  searchButton.disabled = true;
  manualButton.disabled = true;
  finderUnavailable = false;
  finderMapUnavailable = false;
  setFinderMessage('finder.searching');

  const hasMap = ensureHealthcareMap();
  if (hasMap) {
    if (userLocationMarker) healthcareMap.removeLayer(userLocationMarker);
    if (radiusCircle) healthcareMap.removeLayer(radiusCircle);
    radiusCircle = L.circle([lat, lon], {
      radius,
      color: '#3b82f6',
      weight: 1,
      fillColor: '#3b82f6',
      fillOpacity: .06
    }).addTo(healthcareMap);
    userLocationMarker = L.circleMarker([lat, lon], {
      radius: 7, color: '#ffffff', weight: 3, fillColor: '#3b82f6', fillOpacity: 1
    }).addTo(healthcareMap).bindPopup(t('finder.selectedLocation'));
    const zoom = radius <= 1000 ? 15 : radius <= 3000 ? 14 : radius <= 5000 ? 13 : 12;
    healthcareMap.setView([lat, lon], zoom);
  }

  const params = new URLSearchParams({ lat: String(lat), lon: String(lon), radius: String(radius), category });
  try {
    const recent = recentHealthcareSearches.get(searchKey);
    let data;
    if (recent && Date.now() - recent.savedAt < FRONTEND_RESULT_CACHE_MS) {
      data = recent.data;
    } else {
      recentHealthcareSearches.delete(searchKey);
      const response = await fetch(`/api/healthcare/nearby?${params.toString()}`, {
        headers: { Accept: 'application/json' },
        signal: controller.signal
      });
      data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Nearby search failed.');
      if (generation !== searchGeneration) return;
      recentHealthcareSearches.set(searchKey, { data, savedAt: Date.now() });
      if (recentHealthcareSearches.size > 20) {
        recentHealthcareSearches.delete(recentHealthcareSearches.keys().next().value);
      }
    }
    if (generation !== searchGeneration) return;
    nearbyFacilities = Array.isArray(data.facilities) ? data.facilities : [];
    nearbyFacilities.forEach(facility => { delete facility._marker; });
    renderHealthcareResults();
    if (data.cache_status === 'local_snapshot') {
      const importedAt = formatLocalDate(data.last_updated);
      setFinderMessage(nearbyFacilities.length ? 'finder.localWithCount' : 'finder.localEmpty', {
        count: formatNumber(nearbyFacilities.length), date: importedAt
      });
    } else if (data.is_stale || data.stale || data.cache_status === 'stale') {
      setFinderMessage(nearbyFacilities.length ? 'finder.staleWithCount' : 'finder.staleEmpty', {
        count: formatNumber(nearbyFacilities.length), radius: formatNumber(radius / 1000, { maximumFractionDigits: 0 })
      });
    } else if (nearbyFacilities.length) {
      setFinderMessage('finder.freshWithCount', {
        count: formatNumber(nearbyFacilities.length), radius: formatNumber(radius / 1000, { maximumFractionDigits: 0 })
      });
    } else {
      setFinderMessage('finder.freshEmpty');
    }
    if (!hasMap) {
      finderMapUnavailable = true;
      renderFinderMessage();
    }
  } catch (error) {
    if (error.name === 'AbortError' || generation !== searchGeneration) return;
    nearbyFacilities = [];
    facilityLayer?.clearLayers();
    finderUnavailable = true;
    finderMapUnavailable = false;
    renderHealthcareFailure();
    setFinderMessage('finder.loadError', {}, error.message);
  } finally {
    if (generation === searchGeneration) {
      searchController = null;
      activeSearchKey = null;
      searchButton.disabled = false;
      manualButton.disabled = false;
    }
  }
}

function showFinder(finderVisible) {
  $('finder').hidden = !finderVisible;
  $('app').classList.toggle('finder-active', finderVisible);
  $('finderNav').classList.toggle('active', finderVisible);
  $('chatNav').classList.toggle('active', !finderVisible);
  if (finderVisible) {
    $('finderNav').setAttribute('aria-current', 'page');
    $('chatNav').removeAttribute('aria-current');
    requestAnimationFrame(() => healthcareMap?.invalidateSize());
  } else {
    $('chatNav').setAttribute('aria-current', 'page');
    $('finderNav').removeAttribute('aria-current');
  }
}

$('finderNav').addEventListener('click', () => showFinder(true));
$('chatNav').addEventListener('click', () => showFinder(false));

$('searchNearMe').addEventListener('click', () => {
  if (!navigator.geolocation) {
    setFinderMessage('finder.locationUnsupported');
    $('manualLocation').open = true;
    return;
  }

  const button = $('searchNearMe');
  button.disabled = true;
  setFinderMessage('finder.waitingPermission');
  try {
    navigator.geolocation.getCurrentPosition(
      position => {
        button.disabled = false;
        searchHealthcare(position.coords.latitude, position.coords.longitude);
      },
      error => {
        button.disabled = false;
        if (error.code === 1) {
          setFinderMessage('finder.permissionDenied');
        } else if (error.code === 2) {
          setFinderMessage('finder.locationUnknown');
        } else {
          setFinderMessage('finder.locationTimeout');
        }
        $('manualLocation').open = true;
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 30000 }
    );
  } catch {
    button.disabled = false;
    setFinderMessage('finder.locationUnavailable');
    $('manualLocation').open = true;
  }
});

$('manualSearch').addEventListener('submit', event => {
  event.preventDefault();
  searchHealthcare(Number($('manualLat').value), Number($('manualLon').value));
});

$('searchRadius').addEventListener('change', () => {
  if (!currentCoordinates) return;
  if (radiusSearchTimer) clearTimeout(radiusSearchTimer);
  if (searchController) {
    searchController.abort();
    searchController = null;
    activeSearchKey = null;
    searchGeneration += 1;
  }
  radiusSearchTimer = setTimeout(() => {
    searchHealthcare(currentCoordinates.lat, currentCoordinates.lon);
  }, 400);
});

document.querySelectorAll('.category-filter').forEach(button => {
  button.addEventListener('click', () => {
    selectedCategory = button.dataset.category;
    document.querySelectorAll('.category-filter').forEach(filter => {
      const active = filter === button;
      filter.classList.toggle('active', active);
      filter.setAttribute('aria-pressed', String(active));
    });
    renderHealthcareResults();
  });
});
