# Modrinth Downloader
A lightweight, standalone Python program for downloading projects from [Modrinth](https://modrinth.com/).

## Installation
1. Install [Python](https://www.python.org/).
2. Install [requests](https://pypi.org/project/requests/) with `pip install requests`.
3. Download `main.py` from this repository and save it to an empty folder.
4. Run `main.py` to use the program!

## Searching
### Basic Searches
* To search the entire site with no filters, simply write your search term.\
  `Sodium`
* To search just one category, use a Project Type search filter.\
  `Fresh Animations +resourcepack`

### Search Filters
* To add a search filter, type a keyword beginning with `+` in your search term. If there are multiple, projects that match ANY of these will be shown.\
  `your search term +your_search_filter +another_filter`
* Some filters can also use `-` to search for projects that don't match the filter. If there are multiple, projects that match NONE of these will be shown.\
  `your search term -dont_include_this -dont_include_this_either`

### Search Filter List
* Project Type: `+mod`, `+resourcepack`, `+rp`, `+datapack`, `+dp`, `+modpack`, `+mp`, `+plugin`, `+shader`
* Loader: `+bukkit`, `+bungeecord`, `+canvas`, `+fabric`, `+folia`, `+forge`, `+iris`, `+liteloader`, `+modloader`, `+neoforge`, `+optifine`, `+paper`, `+purpur`, `+quilt`, `+rift`, `+spigot`, `+sponge`, `+vanilla`, `+velocity`, `+waterfall`
* Platform: `+/-server`, `+/-client`, `+/-serversupported`, `+/-clientsupported`
* Version: `+v<version>` (Examples: `+v1.12.2`, `+v1.16.5`, `+v1.21`, `+v25w14craftmine`)
* Tag: `+/-t<version>` (Examples: `+tadventure`, `+ttechnology`, `-tcursed`, `-t32x`)

### Sorting Rule
* To change the sorting rule, type a word beginning with "/" in your search term.
* Valid rules: `/relevance` (default), `/downloads`, `/follows`, `/newest`, `/updated`
* Examples:\
  `physics /follows`\
  `/downloads`\
  `create addon /updated`
