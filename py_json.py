# JSON is commonly used with data APIs.

import json

# JSON sample
user_json = '{"first_name":"Ryan", "last_name":"Heida", "age":"24"}'

# Parse to dictionary
user = json.loads(user_json)

print(user)
print(type(user))
print(user['first_name'])


language = {'name':'Python', 'usage':'all fields', 'rate':100}

# Dump to JSON
language_json = json.dumps(language)

print(language_json)






