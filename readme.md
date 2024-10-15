# Py4web scaffolding application

Scaffolding application for Py4web

## Documentation

Work in Progress

## Installation

- Create and start a virtual environment

```bash
  virtualenv -p python3 venv
  source venv/bin/activated
```

- Create a py4web directory and an apps subdirectory

```bash
  mkdir py4web
  cd py4web
  mkdir apps
  cd apps
```

- Clone this repository. Move or rename the appconfig.ini.example file. Edit the necessary parameters

```bash
  git clone https://git.ciditel.net/CIDITEL/py4web_scaffold.git
  cd py4web_scaffold/private
  mv appconfig.ini.example appconfig.ini
```

- Install the requirements

```bash
  cd ..
  pip3 install -r requirements.txt
```

- Go back to the py4web directory and start the app

```bash
  cd ..
  py4web run apps --watch sync
```
    
## License

Do whatever you want with this app. It's yours.
