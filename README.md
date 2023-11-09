# pricedisplay

Terminal Display for the Finnish Power Price


## Building

You can install the dependencies and build the package with Poetry:

`poetry install`

`poetry build`

You can test the build with:

`poetry run python -m pricedisplay`


## Installing

Install the package from PyPI:

`python -m pip install pricedisplay`

Currently you need Python 3.9 or greater.


## Usage

Run the display with the command:

`python -m pricedisplay`

The package creates a settings file config.yml in your config path.

| OS        | Settings Location                             |
|-----------|-----------------------------------------------|
| macOS     | `~/Library/Application Support/pricedisplay/` |
| GNU/Linux | `~/.config/pricedisplay/`                     |
| Windows   | `%APPDATA%\pricedisplay\`                     |

You can also pass your own settings file as an argument:

`python -m pricedisplay --settings PATH`


## Notes

The actual display of the graph depends on your terminal font and colors. For best results you should have UTF-8 encoding and a font which includes unicode East Asian ambiguous characters (in wide format). Some tested combinations are:

| OS        | Terminal         | Font           |           
|-----------|------------------|----------------|
| macOS     | iTerm with Bash  | Hack           |
| GNU/Linux | Gnome with Bash  | Ubuntu Mono    |
| Windows   | Mintty with Bash | Lucida Console | 


## Sample outputs

![sample output minimal](samples/sample_horizontal.png)

![sample output minimal](samples/sample_vertical.png)

![sample output minimal](samples/sample_minimal.png)
