import os
import sys
import yaml
import json
import jinja2
import re

############################################################
# GLOBAL SETTINGS
############################################################
push_to_intersight = False
if 'pushIntersight' in sys.argv:
    push_to_intersight = True

create_import_file = True

# Intersight Keys
api_key_file = 'ApiKey.txt'
secret_key_file = 'SecretKey.txt'

# Version
version = 1
if os.getenv('VERSION') != None:
    version = os.getenv('VERSION')


############################################################
# HELPER FUNCTIONS
############################################################
# Intersight API setup
def get_api_client(api_key_file, api_secret_file, endpoint="https://intersight.com"):
    with open(api_key_file, 'r') as f:
        api_key_id = f.read()

    with open(api_secret_file, 'r') as f:
        api_key = f.read()

    if re.search('BEGIN RSA PRIVATE KEY', api_key):
        # API Key v2 format
        signing_algorithm = intersight.signing.ALGORITHM_RSASSA_PKCS1v15
        signing_scheme = intersight.signing.SCHEME_RSA_SHA256
        hash_algorithm = intersight.signing.HASH_SHA256

    elif re.search('BEGIN EC PRIVATE KEY', api_key):
        # API Key v3 format
        signing_algorithm = intersight.signing.ALGORITHM_ECDSA_MODE_DETERMINISTIC_RFC6979
        signing_scheme = intersight.signing.SCHEME_HS2019
        hash_algorithm = intersight.signing.HASH_SHA256

    configuration = intersight.Configuration(
        host=endpoint,
        signing_info=intersight.signing.HttpSigningConfiguration(
            key_id=api_key_id,
            private_key_path=api_secret_file,
            signing_scheme=signing_scheme,
            signing_algorithm=signing_algorithm,
            hash_algorithm=hash_algorithm,
            signed_headers=[
                intersight.signing.HEADER_REQUEST_TARGET,
                intersight.signing.HEADER_HOST,
                intersight.signing.HEADER_DATE,
                intersight.signing.HEADER_DIGEST,
            ]
        )
    )

    return intersight.ApiClient(configuration)


# Get all definition files
def get_definition_files():
    definitions = {}

    for def_file in os.listdir('./definitions'):
        with open(f"./definitions/{def_file}") as f:
            definitions[f"{def_file}"] = list(yaml.load_all(f, Loader=yaml.FullLoader))
    
    return definitions


# Calculate rollback value
def calculate_rollback(rollback_input,created_tasks):
    if rollback_input == None:
        return None

    rollback = None
    if rollback_input != None:
        moid_ref = None
        for task in created_tasks:
            if task['name'] == rollback_input['task']:
                moid_ref = task['moid']

        rollback = {
            'task_name': rollback_input['task'],
            'task_moid': moid_ref,
            'inputs': []
        }

        for input in rollback_input['inputs']:
            key = list(input.keys())[0]
            value = input[key]

            if type(value) == int:
                pass
            elif 'output.' in value:
                value = value.split('.')[1]
                value = f"${{task.output.{value}}}"

            rollback['inputs'].append({
                'input': key,
                'value': value
            })
    
    return rollback


def calculate_body(input_body):
    if input_body == None:
        return None

    body = json.dumps(document['body'])
    if body == 'null':
        body = None
    else:
        variables = re.findall(r"\$input\.[a-zA-Z0-9_-]+",body)
        for var in variables:
            new_var = "{{ .global.task.input." + f"{var.split('.')[1]}" + " }}"
            body = body.replace(var,new_var)

    return body

# Validate individual element value
def validate_element(value, type, display_name):
    if 'name' not in value or value['name'] == None:
        raise ValueError(f'Task "{display_name}" has an undefined {type} display name')

    if 'reference' not in value or value['reference'] == None:
        raise ValueError(f'Task "{display_name}" has an undefined {type} reference name for "{value["name"]}"')

    if 'type' not in value:
        raise ValueError(f'Task "{display_name}" has an undefined {type} type for "{value["name"]}"')

    if value['type'] not in ['string', 'integer', 'float', 'boolean', 'json']:
        raise ValueError(f'Task "{display_name}" has an unrecognized {type} datatype for "{value["name"]}". Allowed datatypes are string, integer, float, boolean, json.')

    if type == 'output':
        if 'path' not in value or value['path'] == None:
            raise ValueError(f'Task "{display_name}" has an undefined output path for "{value["name"]}"')

# Calculate input values
def calculate_input_values(display_name,required_inputs=[],optional_inputs=[]):
    inputs = []

    if required_inputs != None:
        for input in required_inputs:
            validate_element(input,'input',display_name)
            inputs.append({
                'type': input['type'],
                'display_name': input['name'],
                'reference_name': input['reference'],
                'required': True,
                'description': input['description']
            })

    if optional_inputs != None:
        for input in optional_inputs:
            validate_element(input,'input',display_name)
            inputs.append({
                'type': input['type'],
                'display_name': input['name'],
                'reference_name': input['reference'],
                'required': False,
                'description': input['description']
            })

    return inputs


# Calculate output values
def calculate_output_values(display_name,output_definition):
    outputs = []

    if output_definition != None:
        for output in output_definition:
            validate_element(output,'output',display_name)
            outputs.append({
                'jsonpath': output['path'],
                'type': output['type'],
                'display_name': output['name'],
                'reference_name': output['reference']
            })

    return outputs


# Create Intersight Task definition
def create_task(display_name,reference_name,description,category,target_name,inputs,outputs,rollback,catalog_moid):
    task_render = json.loads(create_template_task.render(
         display_name=display_name,
         reference_name=reference_name,
         description=description,
         category=category,
         target_name=target_name,
         inputs=inputs,
         outputs=outputs,
         rollback=rollback,
         catalog=catalog_moid
    ))

    task_def = WorkflowTaskDefinition(**task_render, _spec_property_naming=True, _configuration=api_client.configuration)
    task_response = workflow_api_instance.create_workflow_task_definition(task_def)
    
    return task_response


# Create Intersight Batch API executor
def create_batch_api_executor(display_name,reference_name,description,method,path,body,outputs,task_definition):
    executor_render = json.loads(create_template_executor.render(
        display_name=display_name,
        reference_name=reference_name,
        description=description,
        method=method,
        path=path,
        body=body,
        outputs=outputs,
        task_definition=task_definition
    ))

    batch_def = WorkflowBatchExecutor(**executor_render, _spec_property_naming=True, _configuration=api_client.configuration)
    return workflow_api_instance.create_workflow_batch_api_executor(batch_def)


############################################################
# INITIALIZATION
############################################################
# Jinja2 setup
env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates/"))
create_template_task = env.get_template("create_template_task.json")
create_template_executor = env.get_template("create_template_executor.json")
import_template_task = env.get_template("import_template_task.json")
import_template_executor = env.get_template("import_template_executor.json")

# Initialize Intersight
if push_to_intersight == True:
    import intersight
    from intersight.api import workflow_api,organization_api
    from intersight.model.workflow_task_definition import WorkflowTaskDefinition
    from intersight.model.workflow_batch_executor import WorkflowBatchExecutor

    api_client = get_api_client(api_key_file, secret_key_file)

    workflow_api_instance = workflow_api.WorkflowApi(api_client)
    organization_api_instance = organization_api.OrganizationApi(api_client)

    # GET default Org Moid: /organization/Organizations
    kwargs = dict(filter="Name eq 'default'")
    default_org_moid = organization_api_instance.get_organization_organization_list(**kwargs).results[0].moid


    # GET catalog Moid: /workflow/Catalogs
    kwargs = dict(filter=f"Organization.Moid eq '{default_org_moid}'")
    catalog_moid = workflow_api_instance.get_workflow_catalog_list(**kwargs).results[0].moid




############################################################
# RUN TASK CREATION
############################################################

# Get definitions
definitions = get_definition_files()

# Iterate over definition files
for definition in definitions:
    import_list = []
    created_tasks = []

    # Iterate over document in definition
    for document in definitions[definition]:
        if document == None:
            print("Skipped document, no task defined")
        else:
            # Document Inputs
            display_name = document['name']
            reference_name = document['reference']
            description = document.get('description')
            category = document['category']
            target_name = document['target_name']
            method = document['method']
            path = document['path']

            # Calculate body
            body = calculate_body(document.get('body'))

            # Calculate input values
            inputs = calculate_input_values(display_name,document.get('required_inputs',[]),document.get('optional_inputs',[]))

            # Calculate output values
            outputs = calculate_output_values(display_name,document.get('outputs'))

            # Calculate rollback value
            rollback = calculate_rollback(document.get('rollback'),created_tasks)

            # Push to Intersight
            if push_to_intersight:
                # POST TASK DEFINITION: /workflow/TaskDefinitions
                task_response = create_task(display_name,reference_name,description,category,target_name,inputs,outputs,rollback,catalog_moid)
                
                created_tasks.append({
                    'name': reference_name,
                    'moid': task_response.moid
                })


                # POST BATCH API EXECUTOR: workflow/BatchApiExecutors
                batch_response = create_batch_api_executor(display_name,reference_name,description,method,path,body,outputs,task_response.moid)

                print(f"Task '{display_name}' updated in system")

            # Append to Output file
            if create_import_file:
                import_list.append(json.loads(import_template_task.render(
                    description=description,
                    display_name=display_name,
                    reference_name=reference_name,
                    category=category,
                    target_name=target_name,
                    inputs=inputs,
                    outputs=outputs,
                    rollback=rollback,
                    version=version
                )))

                import_list.append(json.loads(import_template_executor.render(
                    display_name=display_name,
                    reference_name=reference_name,
                    description=description,
                    method=method,
                    path=path,
                    body=body,
                    outputs=outputs,
                    version=version
                )))

    if create_import_file:
        if not os.path.exists("./import_files/"):
            os.makedirs("./import_files/")
        with open(f"./import_files/{definition.split('.')[0]}.json", "w") as f:
            f.write(json.dumps(import_list))
