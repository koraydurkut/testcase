import json

def handler(event, context):

    http_method = event['httpMethod']
    if http_method == 'GET':
        path_params = event.get('pathParameters', {})
        id_value = path_params.get('id', 'No ID provided')
        response = {
            "statusCode": 200,
            "body": json.dumps(f"Received GET request for document ID: {id_value}")
        }
    elif http_method == 'POST':
        post_body = event.get('body', "{}")
        post_data = json.loads(post_body)
        response = {
            "statusCode": 200,
            "body": json.dumps(f"Received POST request with data: {post_data}")
        }

    else:
        response = {
            "statusCode": 405,
            "body": json.dumps(f"Method {http_method} not allowed")
        }

    return response
