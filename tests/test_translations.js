const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectRoot = path.resolve(__dirname, '..');

function loadI18n(savedLanguage = null) {
  const stored = new Map(savedLanguage ? [['careanywhere-language', savedLanguage]] : []);
  const toggle = {
    textContent: '',
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    title: ''
  };
  const document = {
    documentElement: {
      lang: 'en', dataset: {},
      classList: { add() {}, remove() {} }
    },
    querySelectorAll() { return []; },
    getElementById(id) { return id === 'languageToggle' ? toggle : null; }
  };
  const window = { setTimeout(callback) { callback(); } };
  const localStorage = {
    getItem(key) { return stored.get(key) ?? null; },
    setItem(key, value) { stored.set(key, value); }
  };
  vm.runInNewContext(fs.readFileSync(path.join(projectRoot, 'static/translations.js'), 'utf8'), {
    document, localStorage, window
  });
  return { i18n: window.CareAnywhereI18n, stored, document, toggle };
}

test('language defaults to English and switches both ways with persisted preference', () => {
  const { i18n, stored, document, toggle } = loadI18n();
  assert.equal(i18n.getLanguage(), 'en');
  assert.equal(toggle.textContent, 'বাংলা');
  i18n.setLanguage('bn');
  assert.equal(i18n.getLanguage(), 'bn');
  assert.equal(stored.get('careanywhere-language'), 'bn');
  assert.equal(document.documentElement.lang, 'bn');
  assert.equal(toggle.textContent, 'English');
  i18n.setLanguage('en');
  assert.equal(stored.get('careanywhere-language'), 'en');
  assert.equal(toggle.textContent, 'বাংলা');
});

test('saved Bangla preference is restored and missing translations fall back to English', () => {
  const { i18n } = loadI18n('bn');
  assert.equal(i18n.getLanguage(), 'bn');
  assert.equal(i18n.t('welcome.title'), 'হ্যালো! আজ কীভাবে আপনাকে সাহায্য করতে পারি?');
  assert.equal(i18n.t('a.missing.key'), 'a.missing.key');
});

test('all translated HTML attributes have dictionary entries in both languages', () => {
  const { i18n } = loadI18n();
  const html = fs.readFileSync(path.join(projectRoot, 'templates/index.html'), 'utf8');
  const keys = [...html.matchAll(/data-i18n(?:-[\w-]+)?="([^"]+)"/g)].map(match => match[1]);
  for (const key of new Set(keys)) {
    assert.ok(i18n.translations.en[key], `English translation missing: ${key}`);
    assert.ok(i18n.translations.bn[key], `Bangla translation missing: ${key}`);
  }
});
