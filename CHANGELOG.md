# CHANGELOG


## v0.5.0 (2025-04-18)

### Features

- Various QoL changes
  ([`dc85bde`](https://github.com/Rizhiy/anki-llm-card-fill/commit/dc85bde8f5e5a504da27c722f9331e84612fec0b))

* Allow to set maximum prompt length, to prevent accidental expensive calls * Allow to preview
  actual prompt for specified card * Add basic HTML to Markdown conversion * Remember api key and
  selected mode for each client separately * Retrieve full list of models from API for each client


## v0.4.0 (2025-04-18)

### Features

- Add ability to use LLM from editor window
  ([`2d3d208`](https://github.com/Rizhiy/anki-llm-card-fill/commit/2d3d208056910b03df1c72cc20e45de930902cca))

- Allow updating multiple cards at once from browser
  ([`93a5e12`](https://github.com/Rizhiy/anki-llm-card-fill/commit/93a5e124d8fbd5eb234c02c65f11de7955bf6994))

### Performance Improvements

- Make all calls in separate thread to not block the UI
  ([`3790f4c`](https://github.com/Rizhiy/anki-llm-card-fill/commit/3790f4cac0834a42b6a009e710c5cba0c67fabc2))


## v0.3.0 (2025-03-03)

### Bug Fixes

- Fix update of model list
  ([`27b73ce`](https://github.com/Rizhiy/anki-llm-card-fill/commit/27b73cebe95df2779c3c9a5685e9cc7180063076))

### Chores

- Add default config
  ([`3ede304`](https://github.com/Rizhiy/anki-llm-card-fill/commit/3ede3044c316110f0a942abd6de3569531c6e874))

### Features

- Add more hints and explain how to use in README
  ([`950d3cc`](https://github.com/Rizhiy/anki-llm-card-fill/commit/950d3cc3dc7a53466a914bcd75dca28f6d9e544b))


## v0.2.0 (2025-03-03)

### Chores

- Pass config variables to llm clients
  ([`e4261d4`](https://github.com/Rizhiy/anki-llm-card-fill/commit/e4261d463500e82621805a54278adc337ce93fe2))

### Continuous Integration

- Trying to fix github tests
  ([`2895c20`](https://github.com/Rizhiy/anki-llm-card-fill/commit/2895c200a70f6425373b531169d78ac27efbd04c))

- Update github actions
  ([`a912d9b`](https://github.com/Rizhiy/anki-llm-card-fill/commit/a912d9b0529921c15fa72076d51fbf78c8d80453))

### Features

- Add card update logic
  ([`ef648eb`](https://github.com/Rizhiy/anki-llm-card-fill/commit/ef648ebd0058925fe078044a8fde1443e12792ce))

- Add config and llm clients
  ([`7545c21`](https://github.com/Rizhiy/anki-llm-card-fill/commit/7545c2146bdbb93d637d60fa7a3c21aa92a8a521))

- **config**: Split dialog window into tabs
  ([`06daa84`](https://github.com/Rizhiy/anki-llm-card-fill/commit/06daa848b56f9722eacb0a0e2041f79257d44a68))

### Testing

- Add tests
  ([`99bccb8`](https://github.com/Rizhiy/anki-llm-card-fill/commit/99bccb8e65f3005a3878df2631fcddae28d00e10))


## v0.1.0 (2025-03-02)

### Features

- Add project structure
  ([`94e5a93`](https://github.com/Rizhiy/anki-llm-card-fill/commit/94e5a9359deec46513828cd163d6f5b64c50cabc))

- Init
  ([`f0de671`](https://github.com/Rizhiy/anki-llm-card-fill/commit/f0de6710d656b86973557efb56d573a3b05ec5d1))
