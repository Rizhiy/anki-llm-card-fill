# Anki LLM Card Fill

## Example usage

This addon can query an LLM API with the prompt you specify, and update the fields based on the generated response.

Addon can be configured using "LLM Card Fill" menu in the main bar.

To use it you will need to get an API key from one of the model providers.
Currently Anthropic and OpenAI are supported.
Link to where to get the key is included next to the key field.

Example prompt I use for generating Japanese sentences:

- Given the card with fields:
  - Word
  - Hint
  - Hint translation
- Prompt:

  ```
  I'm learning Japanese and I want you to help me by writing example sentence for word "{Word}".
  Please put furigana after every kanji in square brackets like so: 読[よ]む
  Also, put a space before every kanji. Do not put a space before words that do not require furigana.
  Here is an example of correctly formatted sentence:
  日本[にほん]では 食事[しょくじ]の 後[あと]にお 茶[ちゃ]を 飲[の]むことが 多[おお]いです。
  ```

- Field Descriptions:
  ```
  Hint: An example sentence using the word in Japanese
  Hint translation: English translation of the example sentence
  ```

## Development

Create a virtual environment with your preferred method.
e.g. for conda:

```bash
conda create -n anki-llm-card-fill python=3.9
```

Activate the environment:

```bash
conda activate anki-llm-card-fill
```

Install the dependencies:

```bash
pip install -r ".[dev]"
```

Since Anki doesn't install dependencies automatically, we should keep them to a minimum.

Finally, link/copy the `anki_llm_card_fill` directory to relevant place on your system.
