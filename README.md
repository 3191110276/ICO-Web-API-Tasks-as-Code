# ICO Web API Tasks as Code

![example workflow](https://github.com/3191110276/ICO-Web-API-Tasks-as-Code/actions/workflows/main.yml/badge.svg)

This tool allows you to define Web API Tasks for [Intersight](https://intersight.com) Cloud Orchestrator as Code. It will generate a file that is ready for import into any Intersight Account. This tool should enable experts to quickly build and collaborate on new tasks.

## Get created Tasks
The repository is completely self-contained. Every time someone creates a commit on the main branch, the tool will build a new release using GitHub actions. These builds will contain a file "import_file.zip". You can download this file to get all the tasks ready for import into Intersight. [Click here to download the latest release.](https://github.com/3191110276/ICO-Web-API-Tasks-as-Code/releases/latest/download/import_file.zip)

## Build your own Tasks
To build your own tasks, you have to create a specification in the [./definitions](./definitions) folder. Each definition file will result in a separate JSON file inside of the the Release file "import_file.zip". Tasks inside of the definition files are specified using YAML. The basic structure of a task looks like this:

```yaml
name: Example Name
reference: example_name
description: This is the example description
category: Example
target_name: Example Target
required_inputs:
optional_inputs:
method: GET
path: /example/path
body:
outputs:
rollback:
```

| Entry           | Required | Description                                                                                                                | Possible Values                              |
|-----------------|----------|----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| name            | yes      | The display name of the task presented to the end user                                                                     | Letters (a-z, A-Z), numbers (0-9), hyphen (-), period (.), colon (:), space ( ), single quote ('), forward slash (/), or an underscore (_) - at least 2 characters   | 
| reference       | yes      | The reference name of the task that will be used for internal references                                                   | Letters (a-z, A-Z), numbers (0-9), hyphen (-), period (.), colon (:), or an underscore (_) - at least 2 and at most 64 characters  |
| description     | no       | The description of the task that will be shown to the end user                                                             |                                              |
| category        | yes      | The category in which the task will show up for end users. This makes it easier to find a task for an end user.            |                                              |
| target_name     | yes      | Name of the Web API Target shown when using the task                                                                       | Letters (a-z, A-Z), numbers (0-9), hyphen (-), period (.), colon (:), space ( ) or an underscore (_) - at least 2 characters       |
| required_inputs | no       | The task inputs that are mandatory  |  See below for [Input Definition](#input-definition)     |
| optional_inputs | no       | The task inputs that are optional   |  See below for [Input Definition](#input-definition)     |
| method          | yes      | The method for the HTTP request                                                                                            | GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS |
| path            | yes      | The API path without the domain name | Valid URL path |
| body            | no       | The request body - only necessary for some request methods    | See below for [Body Definition](#body-definition)   |
| outputs         | no       | The outputs of the task based on a JSON response parser     | See below for [Output Definition](#output-definition)    |
| rollback        | no       | The rollback definition - only required if you want to provide an option to undo a task | See below for [Rollback Definition](#rollback-definition) |

### Input Definition
Inputs, both required and optional, are a list. Each entry in that list has to adhere to this format:
```yaml
- name: Input Name
  reference: input_name
  type: string
  description: The description of the input
```

| Entry       | Required | Description                                                                | Possible Values |
|-------------|----------|----------------------------------------------------------------------------|-----------------|
| name        | yes      | The display name for the input which will be shown to the end user         | Letters (a-z, A-Z), numbers (0-9), hyphen (-), period (.), colon (:), space ( ) or an underscore (_) - at least 2 characters |
| reference   | yes      | The reference name for the input which will be used internally in the task | Letters (a-z, A-Z), numbers (0-9), period (.) or an underscore (_) |
| type        | yes      | The datatype that the input will allow                                     | string, integer, float, boolean, json |
| description | no       | The description of the input that will be shown to the end user            |                 |

### Body Definition
The body can be any JSON document. A body definition will look like this:
```yaml
body: >-
  {
    "key_in_json": "value_in_json"
  }
 ```

In addition to static JSON files, you can also use some functions to dynamically adjust the body contents. You can find more information about this in the [Functions in Tasks](#functions-in-tasks) section. 

### Output Definition
Outputs are a list. Each entry in that list has to adhere to this format:
```yaml
- name: Output Name
  reference: output_name
  type: string
  path: $.output
```

| Entry     | Required | Description                                                                                | Possible Values |
|-----------|----------|--------------------------------------------------------------------------------------------|-----------------|
| name      | yes      | The display name for the output which will be shown to the end user                        | Letters (a-z, A-Z), numbers (0-9), hyphen (-), period (.), colon (:), space ( ) or an underscore (_) - at least 2 characters |
| reference | yes      | The reference name for the output which will be used internally in the task                | Letters (a-z, A-Z), numbers (0-9), period (.) or an underscore (_) |
| type      | yes      | The datatype that will be used for creating the output                                     | string, integer, float, boolean, json |
| path      | yes      | The JSONpath that allows us to fetch a specific value from the response sent by the target | Valid [JSONpath](https://github.com/json-path/JsonPath)  |

### Rollback Definition
Rollbacks allow you to refer to a previously defined task using its reference name. Inputs of that task also need to be mapped. For each input that you want to provide in the rollback, you have to map the input of the rollback task to an output of the current task. The target does not have to be mapped.
```yaml
rollback:
  task: TaskName
  inputs:
    - input_name: output.output_name
```

### Functions in Tasks
When defining the path and body in a task definition, you can use functions to dynamically adjust how a task should respond to different inputs. 

| Usage              | Description                                                                                                                                                                               | Code                                                                                                                                       |
|--------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| Task Input         | Directly maps the value of a task input                                                                                                                                                    | {{.global.task.input.NAME}}                                                                                                                |
| Optional variables | Populates everything inside of the function only if the input variable has been provided                                                                                                  | {{with $x := .global.task.input.example}}   {{$x}} {{end}}                                                                                 |
| Condition          | Allows you to specify a condition based on input variables                                                                                                                                | {{if (eq .global.task.input.example VALUE)}}   IF TRUE {{else if eq .global.task.input.example VALUE}}   ELIF TRUE {{else}}   ELSE {{end}} |
| Regex              | Apply a regex pattern to a string to filter out a sub-string. Replace REGEX with your regex pattern. This can be combined with the index feature below to filter out the n-th sub-string. | {{FindAllString .global.task.input.example "REGEX"}}                                                                                       |
| Get n-th entry     | Allows you to get the n-th entry from a list. Replace NUMBER with the position of the list item you want to select.                                                                       | {{index .global.task.input.example NUMBER}}                                                                                                |

## Local development
Every time a commit is created on the main branch of this GitHub repository, a new version will be built and released. This can take more than a minute to complete. To faciliate quicker local development, you can also clone this repository to your local machine for faster development.

Running the script normally will create JSON files for upload in a separate folder. You can also let your script create tasks in Intersight directly. To do this, run your script like this:
```
python main.py pushIntersight
```

You will also have to add two files to your local directory: AccessKey.txt and SecretKey.txt, which contain the access key and secret key for Intersight respectively. Please make sure that you never expose these files, and that you never push them to GitHub!
