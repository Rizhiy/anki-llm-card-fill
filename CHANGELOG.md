# CHANGELOG


## v0.8.2 (2025-07-21)

### Bug Fixes

- Don't crash when loading from empty config
  ([`2e0ec7a`](https://github.com/Rizhiy/anki-llm-card-fill/commit/2e0ec7a7db3a808b122c12cbf2d763b17da63afb))

### Chores

- Improve error logging
  ([`6ec3f05`](https://github.com/Rizhiy/anki-llm-card-fill/commit/6ec3f056ae7c9a3d26c727d15f9070f127bc5410))

- Improve JSON format prompt
  ([`e5306fe`](https://github.com/Rizhiy/anki-llm-card-fill/commit/e5306fe20e781f591a472ad48f10c5f1bd7e05e8))


## v0.8.1 (2025-05-14)

### Bug Fixes

- Don't use create only fields during card update
  ([`517fb2a`](https://github.com/Rizhiy/anki-llm-card-fill/commit/517fb2a8f88ea533ae3775a55a62013cb49e34b1))


## v0.8.0 (2025-05-11)

### Chores

- Add some basic cursor rules
  ([`ddd2e2a`](https://github.com/Rizhiy/anki-llm-card-fill/commit/ddd2e2ab765644503b84026dfada04e255188e0b))

### Features

- Add model input support
  ([`f64680d`](https://github.com/Rizhiy/anki-llm-card-fill/commit/f64680d77e6081a7f83ccdd0b05450ede11aecb1))


## v0.7.0 (2025-05-08)

### Chores

- Improve wording
  ([`889c975`](https://github.com/Rizhiy/anki-llm-card-fill/commit/889c97501aa2e4a0a4bba880d1acd6e24baaacb3))

### Features

- Add interface to create new cards from user input
  ([`0a9e6e4`](https://github.com/Rizhiy/anki-llm-card-fill/commit/0a9e6e49e9315dc71fbcc0ee7ca4f5da5b39c4e8))


## v0.6.0 (2025-05-06)

### Chores

- Remove migration plan and update config.json
  ([`afc1c9d`](https://github.com/Rizhiy/anki-llm-card-fill/commit/afc1c9ddcdcd580d336d4f4e3646fe90775d52ac))

### Features

- Add support for multiple note types
  ([`d3109b1`](https://github.com/Rizhiy/anki-llm-card-fill/commit/d3109b1c48d6f19503a544ad1fa9e9e8346407e3))

- Select field types from note info
  ([`d5b9b56`](https://github.com/Rizhiy/anki-llm-card-fill/commit/d5b9b5654db8a4a578d2cfacbabf0e07f68f316d))

### Refactoring

- Change fields to use individual fields
  ([`8013a9c`](https://github.com/Rizhiy/anki-llm-card-fill/commit/8013a9c0a26f106bd7458a4d148ad7fc109d86f1))

- Implement config manager
  ([`308f915`](https://github.com/Rizhiy/anki-llm-card-fill/commit/308f915aadbf66f3f079b58a2b75d65b7bb65d63))

- Use config manager
  ([`4e9d116`](https://github.com/Rizhiy/anki-llm-card-fill/commit/4e9d11647fd620b085db29bb663eaba237e239e2))


## v0.5.2 (2025-04-18)

### Bug Fixes

- Handle network errors when updating cards
  ([`7afea88`](https://github.com/Rizhiy/anki-llm-card-fill/commit/7afea88828d613a411273a294f5c6536c3c77de1))


## v0.5.1 (2025-04-18)

### Bug Fixes

- Fix calling of the actual api
  ([`071c7ac`](https://github.com/Rizhiy/anki-llm-card-fill/commit/071c7ac51a7d273afe6a160001486bc40d292853))


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
