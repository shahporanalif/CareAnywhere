(() => {
  const translations = {
    en: {
      'page.title': 'CareAnywhere AI — Your AI Medical Assistant',
      'brand.home': 'CareAnywhere AI home',
      'brand.subtitle': 'Your AI Medical Assistant',
      'nav.label': 'Main sections',
      'nav.assistant': 'Assistant',
      'nav.finder': 'Nearby Healthcare',
      'language.button': 'বাংলা',
      'language.switchToBangla': 'Switch language to Bangla',
      'language.switchToEnglish': 'Switch language to English',
      'theme.switchDark': 'Switch to dark mode',
      'theme.switchLight': 'Switch to light mode',
      'chat.new': 'New chat',
      'chat.newTitle': 'Start a new chat',
      'chat.conversation': 'Conversation',
      'chat.inputLabel': 'Your medical question',
      'chat.placeholder': 'Describe your symptoms or ask a question...',
      'chat.send': 'Send message',
      'chat.sending': 'Sending message',
      'chat.thinking': 'Thinking',
      'chat.disclaimer': 'Educational guidance only — not a diagnosis. For severe symptoms, contact emergency services.',
      'chat.error': "Sorry, I couldn't complete that request. {detail}",
      'welcome.title': 'Hello! How can I help you today?',
      'welcome.description': 'Ask medical questions and get educational guidance backed by trusted sources.',
      'welcome.suggestions': 'Suggested questions',
      'welcome.questionHeadache': 'How can I manage a headache?',
      'welcome.questionAllergy': 'What are the symptoms of seasonal allergies?',
      'welcome.questionMedicine': 'How do I read a medicine label?',
      'sources.title': 'Sources',
      'sources.knowledgeBase': 'Knowledge base · PDF page {page}',
      'sources.web': 'Web source',
      'status.checking': 'Checking connection',
      'status.connected': 'Connected',
      'status.setupNeeded': 'Setup needed',
      'status.offline': 'Server offline',
      'status.connectedTitle': 'Assistant is connected',
      'status.setupTitle': 'Configure API keys to enable answers',
      'status.offlineTitle': 'Server is unavailable',
      'tools.image': 'Image',
      'tools.imageTitle': 'Upload an image',
      'tools.camera': 'Camera',
      'camera.use': 'Use camera',
      'tools.voice': 'Voice',
      'tools.voiceTitle': 'Record voice input',
      'tools.stop': 'Stop',
      'tools.listen': 'Listen',
      'tools.listenTitle': 'Read the latest answer aloud',
      'image.preview': 'Selected image preview',
      'image.attached': 'Image attached',
      'image.remove': 'Remove',
      'image.invalidType': 'Choose a PNG, JPEG, or WebP image under 5 MB.',
      'image.readError': 'The image could not be read. Please choose another image.',
      'camera.capture': 'Capture photo',
      'camera.close': 'Close camera',
      'camera.notReady': 'Camera is not ready yet.',
      'api.title': 'API access (optional)',
      'api.tokenPlaceholder': 'API_TOKEN from .env',
      'finder.title': 'Find Nearby Healthcare',
      'finder.description': 'Explore hospitals, clinics, pharmacies and doctors around a location you choose.',
      'finder.searchNearMe': 'Search near me',
      'finder.radius': 'Radius',
      'finder.radius1': '1 km',
      'finder.radius3': '3 km',
      'finder.radius5': '5 km',
      'finder.radius10': '10 km',
      'finder.manualLocation': 'Enter coordinates manually',
      'finder.latitude': 'Latitude',
      'finder.longitude': 'Longitude',
      'finder.latitudeExample': 'e.g. 23.8103',
      'finder.longitudeExample': 'e.g. 90.4125',
      'finder.searchLocation': 'Search this location',
      'finder.filters': 'Filter healthcare facilities',
      'finder.initialMessage': 'Choose “Search near me” or enter coordinates to search.',
      'finder.mapLabel': 'Map of nearby healthcare facilities',
      'finder.mapLegend': 'Map marker legend',
      'finder.yourLocation': 'Your location',
      'finder.clinicDoctor': 'Clinic / doctor',
      'finder.resultsLabel': 'Healthcare search results',
      'finder.nearbyPlaces': 'Nearby places',
      'finder.privacy': 'Your coordinates are used for this nearby lookup, not sent to the AI chat. Map tiles load from OpenStreetMap; opening directions shares both locations with OpenStreetMap.',
      'finder.selectedLocation': 'Your selected location',
      'finder.showOnMap': 'Show {name} on the map',
      'finder.directions': 'Directions ↗',
      'finder.placeCount.one': '{count} place',
      'finder.placeCount.other': '{count} places',
      'finder.unavailableCount': 'Unavailable',
      'finder.noCategoryPlaces': 'No places in this category were found in the selected radius.',
      'finder.noPlaces': 'No healthcare places found. Try a larger radius or another location.',
      'finder.invalidCoordinates': 'Enter a valid latitude and longitude to search.',
      'finder.searching': 'Searching OpenStreetMap for nearby healthcare…',
      'finder.localWithCount': 'Showing {count} places from the local OSM snapshot (imported {date}). This is not live data.',
      'finder.localEmpty': 'The local OSM snapshot (imported {date}) has no facilities at this location. This is not live data.',
      'finder.staleWithCount': 'Showing {count} cached places within {radius} km. Map data may be outdated because providers are unavailable.',
      'finder.staleEmpty': 'The last cached search found no mapped places. Map data providers are unavailable, so this result may be outdated.',
      'finder.freshWithCount': 'Showing {count} places within {radius} km.',
      'finder.freshEmpty': 'No healthcare places were found in this area. Try another radius or location.',
      'finder.mapUnavailable': ' The map could not load; the results are still listed.',
      'finder.resultsUnavailable': 'Healthcare results are unavailable because map data services could not be reached. Try again later.',
      'finder.loadError': 'Could not load nearby healthcare. Please try again.',
      'finder.locationUnsupported': 'Location is not available in this browser. Enter coordinates manually instead.',
      'finder.waitingPermission': 'Waiting for location permission…',
      'finder.permissionDenied': 'Location permission was denied. You can allow it in browser settings or enter coordinates manually.',
      'finder.locationUnknown': 'Your location could not be determined. Enter coordinates manually to continue.',
      'finder.locationTimeout': 'Location lookup timed out. Try again or enter coordinates manually.',
      'finder.locationUnavailable': 'Browser location is unavailable here. Enter coordinates manually to continue.',
      'category.all': 'All',
      'category.hospital': 'Hospital',
      'category.hospitalPlural': 'Hospitals',
      'category.clinic': 'Clinic',
      'category.clinicPlural': 'Clinics',
      'category.pharmacy': 'Pharmacy',
      'category.pharmacyPlural': 'Pharmacies',
      'category.doctors': 'Doctors',
      'category.doctorLabel': 'Doctor / medical practice',
      'category.unknown': 'Healthcare',
      'errors.requestFailed': 'The request could not be completed.',
      'errors.transcriptionFailed': 'Speech transcription failed.',
      'errors.speechUnavailable': 'Speech playback is unavailable.',
      'errors.askFirst': 'Ask a question first.',
      'errors.microphoneUnavailable': 'Microphone unavailable: {detail}',
      'errors.cameraUnavailable': 'Camera unavailable: {detail}',
      'errors.chatNetwork': 'The assistant could not be reached. Please try again.',
      'errors.invalidToken': 'The API token is invalid.',
      'errors.configureKeys': 'Set OPENAI_API_KEY and PINECONE_API_KEY in .env',
      'errors.aiService': 'The AI service failed. Check the server configuration and try again.',
      'errors.transcriptionUnavailable': 'Speech transcription is unavailable.',
      'errors.speechSynthesisUnavailable': 'Speech synthesis is unavailable.',
      'errors.healthcareTimeout': 'Nearby healthcare data is temporarily unavailable because all map data providers timed out. Try again later.',
      'errors.healthcareBusy': 'Map data services are busy. Please wait and try again.',
      'errors.healthcareUnavailable': 'Nearby healthcare search is temporarily unavailable. Please try again later.',
      'errors.healthcareReach': 'Could not reach an available map data service. Please try again later.',
      'errors.healthcareQuery': 'The map data service rejected the nearby search query.',
      'errors.healthcareRateMinute': 'Nearby searches are busy. Please wait a minute and try again.',
      'errors.healthcareRateDay': 'Nearby search daily limit reached. Please try again later.'
    },
    bn: {
      'page.title': 'কেয়ারএনিহোয়্যার এআই — আপনার এআই চিকিৎসা সহকারী',
      'brand.home': 'কেয়ারএনিহোয়্যার এআই হোম',
      'brand.subtitle': 'আপনার এআই চিকিৎসা সহকারী',
      'nav.label': 'প্রধান বিভাগ',
      'nav.assistant': 'সহকারী',
      'nav.finder': 'আশেপাশের স্বাস্থ্যসেবা',
      'language.button': 'English',
      'language.switchToBangla': 'ভাষা বাংলায় পরিবর্তন করুন',
      'language.switchToEnglish': 'ভাষা ইংরেজিতে পরিবর্তন করুন',
      'theme.switchDark': 'ডার্ক মোড চালু করুন',
      'theme.switchLight': 'লাইট মোড চালু করুন',
      'chat.new': 'নতুন চ্যাট',
      'chat.newTitle': 'নতুন চ্যাট শুরু করুন',
      'chat.conversation': 'কথোপকথন',
      'chat.inputLabel': 'আপনার চিকিৎসা-সংক্রান্ত প্রশ্ন',
      'chat.placeholder': 'আপনার উপসর্গ লিখুন বা প্রশ্ন করুন…',
      'chat.send': 'বার্তা পাঠান',
      'chat.sending': 'বার্তা পাঠানো হচ্ছে',
      'chat.thinking': 'উত্তর তৈরি হচ্ছে',
      'chat.disclaimer': 'শুধু শিক্ষামূলক তথ্য—রোগ নির্ণয় নয়। গুরুতর উপসর্গ হলে জরুরি সেবায় যোগাযোগ করুন।',
      'chat.error': 'দুঃখিত, অনুরোধটি সম্পন্ন করা যায়নি। {detail}',
      'welcome.title': 'হ্যালো! আজ কীভাবে আপনাকে সাহায্য করতে পারি?',
      'welcome.description': 'বিশ্বস্ত উৎসভিত্তিক স্বাস্থ্যশিক্ষা পেতে চিকিৎসা-সংক্রান্ত প্রশ্ন করুন।',
      'welcome.suggestions': 'প্রস্তাবিত প্রশ্ন',
      'welcome.questionHeadache': 'মাথাব্যথা কমাতে কী করতে পারি?',
      'welcome.questionAllergy': 'মৌসুমি অ্যালার্জির লক্ষণগুলো কী?',
      'welcome.questionMedicine': 'ওষুধের লেবেল কীভাবে পড়ব?',
      'sources.title': 'তথ্যসূত্র',
      'sources.knowledgeBase': 'জ্ঞানভান্ডার · PDF পৃষ্ঠা {page}',
      'sources.web': 'ওয়েব উৎস',
      'status.checking': 'সংযোগ যাচাই হচ্ছে',
      'status.connected': 'সংযুক্ত',
      'status.setupNeeded': 'সেটআপ প্রয়োজন',
      'status.offline': 'সার্ভার অফলাইন',
      'status.connectedTitle': 'সহকারী সংযুক্ত আছে',
      'status.setupTitle': 'উত্তর চালু করতে API কী কনফিগার করুন',
      'status.offlineTitle': 'সার্ভার পাওয়া যাচ্ছে না',
      'tools.image': 'ছবি',
      'tools.imageTitle': 'ছবি আপলোড করুন',
      'tools.camera': 'ক্যামেরা',
      'camera.use': 'ক্যামেরা ব্যবহার করুন',
      'tools.voice': 'কণ্ঠ',
      'tools.voiceTitle': 'কণ্ঠে বলুন',
      'tools.stop': 'থামান',
      'tools.listen': 'শুনুন',
      'tools.listenTitle': 'সর্বশেষ উত্তরটি শুনুন',
      'image.preview': 'নির্বাচিত ছবির পূর্বরূপ',
      'image.attached': 'ছবি যুক্ত হয়েছে',
      'image.remove': 'সরান',
      'image.invalidType': '৫ MB-এর কম আকারের PNG, JPEG বা WebP ছবি বেছে নিন।',
      'image.readError': 'ছবিটি পড়া যায়নি। অন্য একটি ছবি বেছে নিন।',
      'camera.capture': 'ছবি তুলুন',
      'camera.close': 'ক্যামেরা বন্ধ করুন',
      'camera.notReady': 'ক্যামেরা এখনো প্রস্তুত নয়।',
      'api.title': 'API ব্যবহার (ঐচ্ছিক)',
      'api.tokenPlaceholder': '.env ফাইলের API_TOKEN',
      'finder.title': 'আশেপাশে স্বাস্থ্যসেবা খুঁজুন',
      'finder.description': 'আপনার বেছে নেওয়া স্থানের কাছাকাছি হাসপাতাল, ক্লিনিক, ফার্মেসি ও চিকিৎসক দেখুন।',
      'finder.searchNearMe': 'আমার কাছাকাছি খুঁজুন',
      'finder.radius': 'ব্যাসার্ধ',
      'finder.radius1': '১ কিমি',
      'finder.radius3': '৩ কিমি',
      'finder.radius5': '৫ কিমি',
      'finder.radius10': '১০ কিমি',
      'finder.manualLocation': 'স্থানাঙ্ক লিখুন',
      'finder.latitude': 'অক্ষাংশ',
      'finder.longitude': 'দ্রাঘিমাংশ',
      'finder.latitudeExample': 'যেমন 23.8103',
      'finder.longitudeExample': 'যেমন 90.4125',
      'finder.searchLocation': 'এই স্থানে খুঁজুন',
      'finder.filters': 'স্বাস্থ্যসেবার ধরন বাছুন',
      'finder.initialMessage': '“আমার কাছাকাছি খুঁজুন” চাপুন অথবা স্থানাঙ্ক লিখুন।',
      'finder.mapLabel': 'আশেপাশের স্বাস্থ্যসেবার মানচিত্র',
      'finder.mapLegend': 'মানচিত্রের চিহ্নের ব্যাখ্যা',
      'finder.yourLocation': 'আপনার অবস্থান',
      'finder.clinicDoctor': 'ক্লিনিক / চিকিৎসক',
      'finder.resultsLabel': 'স্বাস্থ্যসেবার অনুসন্ধান ফলাফল',
      'finder.nearbyPlaces': 'কাছাকাছি স্থান',
      'finder.privacy': 'এই অনুসন্ধানের জন্য আপনার স্থানাঙ্ক ব্যবহার করা হয়, এআই চ্যাটে পাঠানো হয় না। মানচিত্র OpenStreetMap থেকে আসে; দিকনির্দেশ খুললে উভয় অবস্থান OpenStreetMap-এর সঙ্গে শেয়ার হয়।',
      'finder.selectedLocation': 'আপনার নির্বাচিত অবস্থান',
      'finder.showOnMap': 'মানচিত্রে {name} দেখুন',
      'finder.directions': 'দিকনির্দেশ ↗',
      'finder.placeCount.one': '{count}টি স্থান',
      'finder.placeCount.other': '{count}টি স্থান',
      'finder.unavailableCount': 'পাওয়া যায়নি',
      'finder.noCategoryPlaces': 'নির্বাচিত ব্যাসার্ধে এই ধরনের কোনো স্থান পাওয়া যায়নি।',
      'finder.noPlaces': 'কোনো স্বাস্থ্যসেবা স্থান পাওয়া যায়নি। বড় ব্যাসার্ধ বা অন্য অবস্থান চেষ্টা করুন।',
      'finder.invalidCoordinates': 'অনুসন্ধানের জন্য সঠিক অক্ষাংশ ও দ্রাঘিমাংশ লিখুন।',
      'finder.searching': 'OpenStreetMap-এ আশেপাশের স্বাস্থ্যসেবা খোঁজা হচ্ছে…',
      'finder.localWithCount': 'স্থানীয় OSM স্ন্যাপশট থেকে {count}টি স্থান দেখানো হচ্ছে (আমদানি: {date})। তথ্যটি সরাসরি হালনাগাদ নয়।',
      'finder.localEmpty': 'স্থানীয় OSM স্ন্যাপশটে (আমদানি: {date}) এই স্থানে কোনো স্বাস্থ্যসেবা নেই। তথ্যটি সরাসরি হালনাগাদ নয়।',
      'finder.staleWithCount': '{radius} কিমির মধ্যে ক্যাশে থাকা {count}টি স্থান দেখানো হচ্ছে। মানচিত্রের তথ্য পুরোনো হতে পারে, কারণ ডেটা সেবা এখন পাওয়া যাচ্ছে না।',
      'finder.staleEmpty': 'সর্বশেষ সংরক্ষিত অনুসন্ধানে কোনো স্থান পাওয়া যায়নি। ডেটা সেবা বন্ধ থাকায় ফলাফলটি পুরোনো হতে পারে।',
      'finder.freshWithCount': '{radius} কিমির মধ্যে {count}টি স্থান দেখানো হচ্ছে।',
      'finder.freshEmpty': 'এই এলাকায় কোনো স্বাস্থ্যসেবা স্থান পাওয়া যায়নি। অন্য ব্যাসার্ধ বা অবস্থান চেষ্টা করুন।',
      'finder.mapUnavailable': ' মানচিত্র লোড হয়নি; তালিকায় ফলাফল আছে।',
      'finder.resultsUnavailable': 'মানচিত্রের ডেটা সেবায় সংযোগ করা যায়নি, তাই ফলাফল পাওয়া যাচ্ছে না। পরে আবার চেষ্টা করুন।',
      'finder.loadError': 'আশেপাশের স্বাস্থ্যসেবা লোড করা যায়নি। আবার চেষ্টা করুন।',
      'finder.locationUnsupported': 'এই ব্রাউজারে অবস্থান পাওয়া যাচ্ছে না। পরিবর্তে স্থানাঙ্ক লিখুন।',
      'finder.waitingPermission': 'অবস্থান ব্যবহারের অনুমতির অপেক্ষায়…',
      'finder.permissionDenied': 'অবস্থানের অনুমতি দেওয়া হয়নি। ব্রাউজার সেটিংসে অনুমতি দিন অথবা স্থানাঙ্ক লিখুন।',
      'finder.locationUnknown': 'আপনার অবস্থান নির্ণয় করা যায়নি। চালিয়ে যেতে স্থানাঙ্ক লিখুন।',
      'finder.locationTimeout': 'অবস্থান নির্ণয়ে সময় শেষ হয়েছে। আবার চেষ্টা করুন অথবা স্থানাঙ্ক লিখুন।',
      'finder.locationUnavailable': 'এখানে ব্রাউজারের অবস্থান সেবা পাওয়া যাচ্ছে না। চালিয়ে যেতে স্থানাঙ্ক লিখুন।',
      'category.all': 'সব',
      'category.hospital': 'হাসপাতাল',
      'category.hospitalPlural': 'হাসপাতাল',
      'category.clinic': 'ক্লিনিক',
      'category.clinicPlural': 'ক্লিনিক',
      'category.pharmacy': 'ফার্মেসি',
      'category.pharmacyPlural': 'ফার্মেসি',
      'category.doctors': 'চিকিৎসক',
      'category.doctorLabel': 'চিকিৎসক / চিকিৎসাকেন্দ্র',
      'category.unknown': 'স্বাস্থ্যসেবা',
      'errors.requestFailed': 'অনুরোধটি সম্পন্ন করা যায়নি।',
      'errors.transcriptionFailed': 'কণ্ঠের কথা লিখে নেওয়া যায়নি।',
      'errors.speechUnavailable': 'উত্তর শোনার সুবিধা এখন পাওয়া যাচ্ছে না।',
      'errors.askFirst': 'আগে একটি প্রশ্ন করুন।',
      'errors.microphoneUnavailable': 'মাইক্রোফোন ব্যবহার করা যাচ্ছে না: {detail}',
      'errors.cameraUnavailable': 'ক্যামেরা ব্যবহার করা যাচ্ছে না: {detail}',
      'errors.chatNetwork': 'সহকারীর সঙ্গে সংযোগ করা যায়নি। আবার চেষ্টা করুন।',
      'errors.invalidToken': 'API টোকেনটি সঠিক নয়।',
      'errors.configureKeys': '.env ফাইলে OPENAI_API_KEY ও PINECONE_API_KEY সেট করুন',
      'errors.aiService': 'এআই সেবায় সমস্যা হয়েছে। সার্ভার কনফিগারেশন যাচাই করে আবার চেষ্টা করুন।',
      'errors.transcriptionUnavailable': 'কণ্ঠ থেকে লেখা তৈরির সেবা পাওয়া যাচ্ছে না।',
      'errors.speechSynthesisUnavailable': 'কণ্ঠ তৈরি করার সেবা পাওয়া যাচ্ছে না।',
      'errors.healthcareTimeout': 'সব মানচিত্র সেবার অনুরোধের সময় শেষ হয়েছে। আশেপাশের স্বাস্থ্যসেবা তথ্য এখন পাওয়া যাচ্ছে না। পরে আবার চেষ্টা করুন।',
      'errors.healthcareBusy': 'মানচিত্রের ডেটা সেবা ব্যস্ত। একটু পরে আবার চেষ্টা করুন।',
      'errors.healthcareUnavailable': 'আশেপাশের স্বাস্থ্যসেবা অনুসন্ধান এখন পাওয়া যাচ্ছে না। পরে আবার চেষ্টা করুন।',
      'errors.healthcareReach': 'কোনো মানচিত্র ডেটা সেবায় সংযোগ করা যায়নি। পরে আবার চেষ্টা করুন।',
      'errors.healthcareQuery': 'মানচিত্র ডেটা সেবা অনুসন্ধানের অনুরোধ গ্রহণ করেনি।',
      'errors.healthcareRateMinute': 'অনেক অনুসন্ধান হচ্ছে। এক মিনিট অপেক্ষা করে আবার চেষ্টা করুন।',
      'errors.healthcareRateDay': 'আজকের কাছাকাছি অনুসন্ধানের সীমা শেষ। পরে আবার চেষ্টা করুন।'
    }
  };

  let language = 'en';
  try {
    language = localStorage.getItem('careanywhere-language') === 'bn' ? 'bn' : 'en';
  } catch {}

  function t(key, values = {}) {
    const template = translations[language][key] ?? translations.en[key] ?? key;
    return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => (
      Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match
    ));
  }

  function applyTranslations(root = document) {
    root.querySelectorAll('[data-i18n]').forEach(element => {
      element.textContent = t(element.dataset.i18n);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    root.querySelectorAll('[data-i18n-title]').forEach(element => {
      element.title = t(element.dataset.i18nTitle);
    });
    root.querySelectorAll('[data-i18n-aria-label]').forEach(element => {
      element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel));
    });
    root.querySelectorAll('[data-i18n-alt]').forEach(element => {
      element.alt = t(element.dataset.i18nAlt);
    });
    document.documentElement.lang = language;
    document.documentElement.dataset.language = language;

    const toggle = document.getElementById('languageToggle');
    if (toggle) {
      toggle.textContent = t('language.button');
      const label = language === 'en' ? t('language.switchToBangla') : t('language.switchToEnglish');
      toggle.setAttribute('aria-label', label);
      toggle.title = label;
    }
  }

  function setLanguage(nextLanguage) {
    if (nextLanguage !== 'en' && nextLanguage !== 'bn') nextLanguage = 'en';
    if (nextLanguage === language) return;
    language = nextLanguage;
    try { localStorage.setItem('careanywhere-language', language); } catch {}
    document.documentElement.classList.add('language-changing');
    applyTranslations();
    window.setTimeout(() => document.documentElement.classList.remove('language-changing'), 180);
  }

  function getLanguage() {
    return language;
  }

  window.CareAnywhereI18n = { translations, t, setLanguage, getLanguage, applyTranslations };
  applyTranslations();
})();
