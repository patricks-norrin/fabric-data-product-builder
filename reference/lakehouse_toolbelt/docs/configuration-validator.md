## Configuration validator

The validator checks that a data product configuration is valid before it is used to initialize a data product.

It currently validates three things:

1. **Dataset names are unique**
   - Each dataset in the data product configuration must have a unique `dataset_name`
   - Duplicate dataset names are reported as validation errors

2. **Source configuration attributes are supported**
   - Each dataset may contain a `source_configuration`.
   - The validator checks that all attributes in `source_configuration` are allowed
   - Allowed attributes come from:
     - Class default source configuration attributes
     - Optional project-specific allowed extra attributes

3. **Publish configuration attributes are supported**
   - Each dataset may contain a `publish_configuration`.
   - The validator checks that all attributes in `publish_configuration` are allowed
   - Allowed attributes come from:
     - Class default publish configuration attributes
     - Optional project-specific allowed extra attributes

Configuration validator is called when a data product is initialized. It returns a list of errors (if any), detailing the issue. Data product initialization will fail, if issues are found.



## Project-specific configuration

The validator can optionally use a project-specific configuration file to allow additional attributes that are not part of the default class attributes. It looks for the project-specific configuration file and uses it if one is found.

This is useful when a specific project needs extra configuration keys, for example:

```json
{
  "source_configuration": {
    "allowed_extra_attributes": [
      "pagination_type", "watermark_delay_minutes", "initial_load_date"
    ]
  },
  "publish_configuration": {
    "allowed_extra_attributes": [
      "history_included", "confidential_columns_included"
    ]
  }
}
```

<b>Fabric:</b> Toolbelt expects to find file "project_configuration.json" in "lh_workspace_shared_resources/Files/configuration/data_product/project_configuration"
<b>Databricks:</b> Not implemented



## Related Pages
- [Configuration Reference](configuration-reference.md)