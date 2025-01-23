# InfoCollection

## Properties

- **`tag`** *(string)*: Must be one of: `["twfy", "publicwhip"]`. Default: `"twfy"`.
- **`items`** *(array, required)*
  - **Items**
    - **Any of**
      - : Refer to *[#/$defs/ConsInfo](#%24defs/ConsInfo)*.
      - : Refer to *[#/$defs/PersonInfo](#%24defs/PersonInfo)*.
## Definitions

- <a id="%24defs/ConsInfo"></a>**`ConsInfo`** *(object)*: Can contain additional properties.
  - **`tag`** *(string)*: Must be: `"consinfo"`. Default: `"consinfo"`.
  - **`canonical`** *(string, required)*
- <a id="%24defs/PersonInfo"></a>**`PersonInfo`** *(object)*: Can contain additional properties.
  - **`tag`** *(string)*: Must be: `"personinfo"`. Default: `"personinfo"`.
  - **`person_id`** *(string, required)*
