Welcome to Planet App, a restful backend for managing users and groups
See specification.md for availiable features

run all commands from the root of the project.

### setup
for best results, create a python virtualenv before installing the
dependencies and running the app.
A very useful project for setting up virtual env is
https://github.com/brainsik/virtualenv-burrito

```
> mkvirtualenv planet_app
> pip install --upgrade -r requirements.txt
```
### quickstart
```
> python utils/create_tables.py planet.db
> python app/planet_app.py
```
### create a user and then fetch that user
```
> curl -X POST -d '{"first_name": "christine", "last_name": "donovan", "userid": "cdonovan", "groups": ["photoclub", "bikeclub"]}' http://127.0.0.1:5000/users
> curl http://127.0.0.1:5000/users/cdonovan
```

### run tests, everything in specification.md is validated here.
```
> python tests/integration_tests.py
```
### set a custom database file
```
> export DATABASE=staging.db; python app/planet_app.py
```

### rebuild a database
```
> rm planet.db
> python utils/create_tables.py planet.db
```
