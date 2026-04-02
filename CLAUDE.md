# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

FreshPointParser is a pure HTML parser library for [my.freshpoint.cz](https://my.freshpoint.cz) — a Czech vending machine service that provides snacks, lunches, and desserts at company locations. FreshPoint has no public API, so this library extracts product and location data directly from their webpage HTML.

**The library's contract is simple:**
```python
parse_product_page(html: str | bytes) -> ParseResult[ProductPage]
parse_location_page(html: str | bytes) -> ParseResult[LocationPage]
```

No HTTP client is included by design. The caller fetches HTML however they choose (httpx, requests, async, sync — all outside scope). The library owns only the HTML → structured model conversion.

---

## Core Design Philosophy: Best-Effort Parsing

Raw HTML from an external site is inherently unstable. The site structure can change without notice, individual fields may be missing or malformed, and the library has no control over what it receives. The core principle is: **losing a field is better than losing the entire result.**

This philosophy is implemented at two distinct levels:

### Level 1 — Extraction (parser layer)

`_safe_parse()` in `parsers/_base.py` is the universal exception firewall. Every field extraction call routes through it:

```python
def _safe_parse(self, parser_func, *args, **kwargs):
    try:
        return parser_func(*args, **kwargs)
    except FreshPointParserError as err:
        # Expected extraction failure — field missing or malformed
        self._context.register_error(err)
        return None
    except Exception as exc:
        # Unexpected failure — wrap as ParseError to preserve __cause__
        err = ParseError(f'Unexpected error: {exc}')
        err.__cause__ = exc
        logger.warning('Unexpected exception wrapped as ParseError', exc_info=True)
        self._context.register_error(err)
        return None
```

When extraction fails for any reason, `None` is returned for that field and the error is recorded. The parse continues. This mirrors Parsel's philosophy: absence is signalled via return value, never raised to the caller.

Extraction methods (`ProductHTMLParser.find_*`) deliberately use exceptions internally — they raise `ParseError` on failure. This keeps the happy-path code clean (no nested `if result is None` checks). `_safe_parse` translates these at the boundary.

### Level 2 — Validation (model layer)

`BestEffortModel` in `models/_base.py` handles the case where data was extracted successfully but fails Pydantic validation (type mismatch, constraint violation, or cross-field validator failure). It uses `model_validator(mode='wrap')`:

```python
@model_validator(mode='wrap')
@classmethod
def _safe_validate(cls, data, handler, info):
    try:
        return handler(data)
    except ValidationError as e:
        # Strip the failing fields, retry with their defaults
        failed_fields = {err['loc'][0] for err in e.errors() if err.get('loc')}
        cleaned = {k: v for k, v in data.items() if k not in failed_fields}
        return handler(cleaned)
```

This is field-level partial recovery: a product with an invalid price still has its name, quantity, and allergens. The entire model is not discarded. Errors flow into `ParseContext` and surface in `ParseResult.metadata.errors`.

**Why `mode='wrap'`?** All fields are already `Optional` with `None` defaults, which handles missing data. But `Optional` alone fails when data is *present* but invalid — e.g. `price_curr=-5.0` raises `ValidationError` on `NonNegativeFloat` even though the field has a default. The wrap-validator catches that `ValidationError`, strips the failing fields, and retries with their defaults — giving field-level partial recovery for all failure categories regardless of whether data is absent or logically invalid.

**Why two levels?** Extraction failures ("the HTML didn't have what we expected") and validation failures ("the data was present but logically invalid") are semantically different failure modes. An extraction failure signals a site structure change; a validation failure signals a data quality issue. Keeping them separate preserves this diagnostic information.

### Error surfacing

Every soft error — whether from extraction or validation — is appended to `ParseContext.errors` and surfaced as `ParseResult.metadata.errors`. Nothing is silently discarded. **Silence means success**: an empty `metadata.errors` list means the parse was clean.

`ParseResult.metadata.errors` is `List[Exception]` because it contains both `FreshPointParserError` (extraction) and `pydantic.ValidationError` (validation). The original exception is always preserved via `__cause__` on wrapped errors.

---

## Architecture

```
src/freshpointparser/
├── __init__.py              # Public API
├── exceptions.py            # FreshPointParserError, ParseError
├── _utils.py                # normalize_text(), root logger
├── models/
│   ├── _base.py             # BestEffortModel, BaseItem, BasePage
│   ├── _product.py          # Product, ProductPage, comparison dataclasses
│   ├── _location.py         # Location, LocationPage, LocationCoordinates
│   ├── types.py             # Re-exports of auxiliary types
│   └── __init__.py
└── parsers/
    ├── _base.py             # ParseContext, ParseMetadata, ParseResult,
    │                        # BasePageHTMLParser
    ├── _product.py          # ProductHTMLParser, ProductPageHTMLParser
    ├── _location.py         # LocationPageHTMLParser
    └── __init__.py
```

### Models layer

**`BestEffortModel`** — base for all data models. Provides the wrap-validator recovery described above. Exported from `freshpointparser.models` for users who want to build custom models with the same behaviour.

**`BaseItem`** — base for individual items (`Product`, `Location`). Provides:
- `id_: Optional[str]` — trailing underscore is the Python convention for avoiding `id()` builtin clash; `validation_alias='id'` and `serialization_alias='id'` handle the rename (split aliases are a Pyright/Pylance workaround).
- `model_diff(other)` — field-by-field comparison returning `FieldDiffMapping`.

**`BasePage[TItem]`** — generic container for a page of items. Provides:
- `item_diff(other, exclude_missing=False)` — cross-page diff by item ID, returns `ModelDiffMapping`.
- `find_item(constraint)` / `find_items(constraint)` — search by attribute dict or callable predicate.
- `iter_item_attr(attr, default?, *, unique=False, hashable=True)` — iterate over a single attribute across all items, with optional deduplication.
- `is_newer_than(other, precision?)` — three-valued return: `True`, `False`, or `None` (equal). Precision truncates to `'s'`, `'m'`, `'h'`, `'d'`.
- `recorded_at: datetime` — populated from `ParseContext.parsed_at` at parse time.

**`Product`** — fields extracted from product `<div>` elements. All fields are `Optional` with `None` defaults. Key properties (computed, not stored): `price` (curr if set, else full), `discount_rate`, `is_on_sale`, `is_available`, `is_sold_out`, `is_last_piece`. `compare_quantity(other)` and `compare_price(other)` return `ProductQuantityChange` / `ProductPriceChange` dataclasses describing transitions (e.g., `is_depleted`, `has_sale_started`). The comparison is symmetric — either product can be `self`.

Two non-obvious constraints:
- `price_curr` cannot exceed `price_full` (enforced by `_validate_price_curr` field validator). When violated on direct model construction, `BestEffortModel` drops `price_curr` and retries — `price_full` is preserved, `price_curr` becomes `None`. This validator never fires through the parser because `ProductHTMLParser.find_price()` already checks this.
- `is_promo: Optional[bool]` is parsed from `data-isPromo` but is **unreliable** as a site data quality issue — a product can be on sale without `is_promo=True` and vice versa. Do not use `is_promo` to infer discount status; use `is_on_sale` instead.

**`Location`** — fields extracted from the embedded JSON. Uses `AliasChoices` because the JSON uses short keys (`lat`, `lon`, `username`, `discount`, `active`, `suspended`) while the model uses descriptive names.

**`types.py`** — re-exports auxiliary types: `FieldDiff`, `FieldDiffMapping`, `ModelDiffMapping`, `ValidationContext`, `LocationCoordinates`, `ProductQuantityChange`, `ProductPriceChange`. Import from `freshpointparser.models.types`.

### Parsers layer

**`ParseContext`** — a dataclass that holds a `parsed_at` timestamp and accumulates errors during a parse. It implements the `ValidationContext` protocol, so it can be passed directly as Pydantic's `context=` parameter. `BestEffortModel` calls `context.register_error(err)` during validation. This is the coupling mechanism between model validation and parser error collection.

**`ParseMetadata`** — frozen dataclass returned in every `ParseResult`. Contains `content_digest` (SHA-1 bytes), `parsed_at`, `from_cache`, and `errors`. Exported from `freshpointparser.parsers`.

**`ParseResult[TPage]`** — the top-level return type of every `parse()` call. Contains `page` and `metadata`. `result.errors` is a convenience forwarding to `result.metadata.errors`. Exported from `freshpointparser.parsers`.

**`BasePageHTMLParser[TPage]`** — abstract base for both parsers. Manages:
- SHA-1 content hashing: `parse()` compares the hash of new content against the last-seen hash. If unchanged, `from_cache=True` is set and the previous result is returned immediately without re-parsing.
- `_parse_page_content()` is the abstract method subclasses implement.
- `parse()` always returns a deep copy (`model_copy(deep=True)`) so mutations to `result.page` cannot affect the parser's internal cache.

**`ProductHTMLParser`** — a stateless class of `@classmethod`s. Each method extracts one product attribute from a BS4 `Tag`. The class (rather than module-level functions) groups the extraction logic and allows subclassing to override individual methods for custom HTML structures. Key implementation details:
- `find_category()` looks for the preceding `<h2>` sibling — category is not a `data-*` attribute but a section header in the HTML.
- `find_quantity()` matches Czech stock strings via regex: `^((posledni)|(\d+))\s(kus|kusy|kusu)!?$`. "posledni kus" = last piece = quantity 1.
- `find_price()` finds all text nodes matching `^\d+\.\d+$` within the product `<div>`. One match = regular price (full == curr). Two matches = discounted price (first is full, second is current).
- `find_allergens()` parses `data-allergens` into `List[str]` by splitting on `','`. Empty string → `[]`. Missing attribute → raises `ParseError` (caught by `_safe_parse` → `None`).

**`ProductPageHTMLParser`** — the main product parser. Extracts `location_id` from a `deviceId = "..."` JavaScript variable and `location_name` from the `<title>` tag. Products are found via `find_all('div', class_='product')`.

**`LocationPageHTMLParser`** — the location parser. Location data is embedded as a JavaScript string variable: `devices = "[{\"prop\":{...}}]";`. This requires double JSON parsing: the outer `json.loads` un-escapes the JS string; the inner `json.loads` parses the JSON array. Only the `prop` key of each item is used — the `location` key is confirmed to be a duplicate of `prop` data in a different format.

### Exceptions

```
FreshPointParserError
└── ParseError
```

`ParseError` is raised for all extraction and structural failures. No subclasses — all `ParseError` instances are extraction/structural failures with no semantic distinction callers need to handle differently.

### Utilities

`normalize_text(text: Any) -> str` — converts any value to lowercase ASCII by stripping whitespace, running `unidecode()` (removes Czech diacritics: `ě→e`, `š→s`, `ř→r`, etc.), then `casefold()`. Returns `''` for `None`. Used for `name_lowercase_ascii` and `address_lowercase_ascii` properties to enable case/diacritic-insensitive search.

---

## Public API

Everything a user needs is importable from public modules (no `_private` imports required):

```python
# Top-level convenience
from freshpointparser import (
    parse_product_page,       # stateless, creates fresh parser each call
    parse_location_page,
    get_product_page_url,     # builds https://my.freshpoint.cz/device/product-list/<id>
    get_location_page_url,    # returns https://my.freshpoint.cz
    logger,                   # root logger for the library
)

# Models
from freshpointparser.models import (
    Product, ProductPage,
    Location, LocationPage,
    BestEffortModel,           # for custom model subclassing
    BaseItem, BasePage,
)
from freshpointparser.models.types import (
    ProductQuantityChange, ProductPriceChange,
    FieldDiff, FieldDiffMapping, ModelDiffMapping,
    LocationCoordinates, ValidationContext,
)

# Parsers (when stateful caching is needed)
from freshpointparser.parsers import (
    ProductPageHTMLParser,     # stateful, reuse instance for SHA-1 caching
    LocationPageHTMLParser,
    BasePageHTMLParser,        # for custom parser subclassing
    ParseResult, ParseMetadata,
)
```

The stateless `parse_product_page(html)` creates a new parser on every call (no caching). For polling scenarios where the same page is fetched repeatedly, reuse a `ProductPageHTMLParser` instance — `parse()` will return cached results when content hasn't changed.

---

## Development Setup

```bash
uv sync          # install all dependencies into .venv/
```

The virtual environment is at `.venv/` in the project root. The build backend is `uv_build`. **Target Python versions: 3.8–3.14.** The minimum is 3.8; the project is tested against all versions in that range via tox.

The active development branch is **`dev`**. `main` tracks stable releases. Work on `dev`; merge to `main` only for releases.

`docs/superpowers/` is gitignored — local design specs and notes live there, never commit them.

---

## Commands

### Testing
```bash
# Run all tests (excluding live parser tests)
pytest tests -m "not is_parser_up_to_date"

# Run a single test file
pytest tests/models/test_models_product.py

# Run live parser tests (require FreshPoint website to be up)
# Range of product page IDs is intentionally narrow (range(10, 30)) to keep
# runtime short — adjust manually when spot-checking different IDs
pytest tests -m "is_parser_up_to_date"

# Run via tox for a specific Python version
tox -e py313-test
```

### Linting & Formatting
```bash
ruff format src tests --check   # check only
ruff format src tests           # auto-format
ruff check src tests            # lint
mypy src                        # type checking
tox -e lint                     # all lint checks
```

## Code Style

- Single quotes throughout (ruff-enforced).
- Google-style docstrings.
- Line length: 88 characters.
- `disallow_untyped_defs = true` for `src/`; relaxed for tests.
- Tests relax `ANN`, `D10x`, `S101`, `PLC0415` rules.
- In `except` clauses: use `err` when the exception class reads as "Error" (e.g. `except ParseError as err`), `exc` when it reads as "Exception" (e.g. `except Exception as exc`). Never single-letter names.
- In log and exception messages, identifiers (IDs, names, function names, field names, etc.) must be wrapped in single quotes: `"func '%s' failed"` not `"func %s failed"`.
- Code examples in docstrings use fenced Markdown blocks with a language tag — **not** RST ``::`` blocks:
  ```
  Example:
      ```python
      result = parse_product_page(html)
      ```
  ```
- In docstrings, inline code/monospace uses double backticks:
  ```
  ``correct``   ✓
  `wrong`       ✗
  ```

## Docstrings

- Use imperative mood in summary lines: "Parse the page", not "Parses the page".
- Properties use descriptive style: `"""The effective selling price."""`, not imperative. **Never add `Args:`, `Returns:`, or `Raises:` sections to a property docstring** — a property takes no arguments and its return value is described by the summary line itself.
- Pydantic model fields are documented in **both** `Field(description=...)` and a standalone docstring below the field definition. Both must be present and carry identical text. When polishing a field, update both together.
- Don't restate the class or method name. If `ParseError` already communicates meaning, the docstring adds context beyond what the name says — it doesn't paraphrase it.
- Describe purpose, not implementation. Don't mention base classes, internal patterns, or third-party tools unless essential.
- Module docstrings describe the module's responsibility, not its contents. Write what it *does*, not what it currently contains.

## Logging

- Root logger has a `NullHandler` — library best practice; callers configure their own handlers.
- Log expected actions **before** they happen, in present tense. Add a follow-up log after only if the action can fail or has important results worth surfacing.
- Use `%`-style formatting in log calls (deferred interpolation): `logger.debug("Parsing '%s'", name)`.
- Identifiers in log messages must be wrapped in single quotes (see Code Style above).

## Test Structure

Each test file corresponds to exactly one source module and mirrors its path under `tests/`:

```
src/freshpointparser/models/_base.py     -> tests/models/test_models_base.py
src/freshpointparser/models/_product.py  -> tests/models/test_models_product.py
src/freshpointparser/models/_location.py -> tests/models/test_models_location.py
src/freshpointparser/parsers/_base.py    -> tests/parsers/test_parsers_base.py
src/freshpointparser/parsers/_product.py -> tests/parsers/test_parsers_product.py
src/freshpointparser/parsers/_location.py-> tests/parsers/test_parsers_location.py
src/freshpointparser/_utils.py           -> tests/utils/test_utils.py
```

- No `__init__.py` in test directories — pytest discovers tests as namespace packages.
- Use snake_case field names when constructing Pydantic models in tests (not camelCase aliases). Use `model_validate()` with camelCase data only when specifically testing alias behaviour.
- Test helper functions and module-level constants are not private — no underscore prefix.
- Use `pytest.param(..., id="...")` for all parametrized cases.
- `is_parser_up_to_date` marker — live tests against the real site. Skipped by default.
- Fixture files (`tests/parsers/`): `product_page.html` / `product_page.json` / `product_page_meta.json` (location 296, "Elektroline"), `location_page.html` / `location_page.json` / `location_page_meta.json`. Refresh periodically when the site HTML structure changes significantly.

## Agent Guidelines

- Be direct. Lead with the action or answer, not preamble.
- Fix typos and awkward phrasing on sight — do not leave them for a follow-up.
- Consider second-order effects. Think about what actually happens when a command runs or a pattern is applied.
- Do not transplant patterns from other codebases without verifying they fit this project's architecture.
- Do not over-abstract. Introduce abstractions only when there is a concrete second use case.
- Prefer reversible decisions. If unsure whether something belongs, implement it in a way that is easy to remove.
- Describe what *is*, not what *is not*. Stating negatives reads as a limitation warning.
- Trim prose aggressively. State the point once, directly.
- Do not make unverified factual claims about external systems. Verify or phrase conservatively.
