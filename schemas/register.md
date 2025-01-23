# Register

## Properties

- **`tag`** *(string)*: Must be one of: `["twfy", "publicwhip"]`. Default: `"twfy"`.
- **`person_entries`** *(array, required)*
  - **Items**: Refer to *[#/$defs/PersonEntry](#%24defs/PersonEntry)*.
## Definitions

- <a id="%24defs/Category"></a>**`Category`** *(object)*
  - **`tag`** *(string)*: Must be: `"category"`. Default: `"category"`.
  - **`type`** *(string, required)*
  - **`name`** *(string, required)*
  - **`records`** *(array, required)*
    - **Items**: Refer to *[#/$defs/Record](#%24defs/Record)*.
- <a id="%24defs/Item"></a>**`Item`** *(object)*
  - **`tag`** *(string)*: Must be: `"item"`. Default: `"item"`.
  - **`class`**: Default: `null`.
    - **Any of**
      - *string*
      - *null*
  - **`contents`**: Refer to *[#/$defs/MixedContentHolder](#%24defs/MixedContentHolder)*.
- <a id="%24defs/MixedContentHolder"></a>**`MixedContentHolder`** *(object)*
  - **`text`** *(string, required)*
  - **`raw`** *(string, required)*
- <a id="%24defs/PersonEntry"></a>**`PersonEntry`** *(object)*
  - **`tag`** *(string)*: Must be: `"regmem"`. Default: `"regmem"`.
  - **`person_id`** *(string, required)*
  - **`memberid`**: Default: `null`.
    - **Any of**
      - *string*
      - *null*
  - **`membername`** *(string, required)*
  - **`date`** *(string, format: date, required)*
  - **`record`**: Default: `null`.
    - **Any of**
      - : Refer to *[#/$defs/Record](#%24defs/Record)*.
      - *null*
  - **`categories`** *(array)*
    - **Items**: Refer to *[#/$defs/Category](#%24defs/Category)*.
- <a id="%24defs/Record"></a>**`Record`** *(object)*
  - **`tag`** *(string)*: Must be: `"record"`. Default: `"record"`.
  - **`class`**: Default: `null`.
    - **Any of**
      - *string*
      - *null*
  - **`items`** *(array, required)*
    - **Items**: Refer to *[#/$defs/Item](#%24defs/Item)*.
