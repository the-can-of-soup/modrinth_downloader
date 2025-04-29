from __future__ import annotations
import traceback
import requests
import json
import math
import time

# QUERY FORMAT
#
# Write your search string normally. For search filters, add a word that begins with "+" or "-"
# to filter for or against an attribute. Attributes are split into groups called "facets".
#
# FACETS
#
# Project Type
#     "mod", "resourcepack" OR "rp", "datapack" OR "dp", "modpack" OR "mp", "plugin", "shader"
# Loader
#     "bukkit", "bungeecord", "fabric", "folia", "forge", "neoforge", "paper",
#     "purpur", "quilt", "spigot", "velocity", "waterfall"
# Platform
#     "server", "client", "serverrequired", "clientrequired"
# Version
#     Use the letter "v" and then the Minecraft version. Examples: "v1.20.1", "v23w14a_or_b"
#     NOTE: Versions cannot be excluded with "-"
#
# The search will return projects that match ANY of the "+" attributes AND NONE of the "-" attributes
# for EACH FACET.
#
# EXAMPLES
#
# The filters "+forge +mod +rp -dp -mp -quilt" will return projects that meet the following:
# is a mod OR a resourcepack, AND is not a datapack NOR a modpack, AND is for Forge, AND is not for Quilt.
# Note that "+mod", "+rp", "-dp", and "-mp" get lumped together because they are all part of the "Project
# Type" facet. "+forge" and "-quilt" also are in their own "Loader" facet and so get handled separately.
#
# The query "trajectory -serverrequired +neoforge +mod +v1.21.1" will search for NeoForge mods for 1.21.1
# that do not require a server (meaning they are client-side) with the word "trajectory".
#
# The query "teleport +server" will search for projects that support a server-side version with the
# word "teleport".

LOADERS: list[str] = ['bukkit', 'bungeecord', 'fabric', 'folia', 'forge', 'neoforge', 'paper',
                      'purpur', 'quilt', 'spigot', 'velocity', 'waterfall']
PAGE_SIZE: int = 20

def truncate(text: str, width: int = 20, add_whitespace: bool = True) -> str:
    if len(text) <= width:
        if add_whitespace:
            return text.ljust(width)
        return text
    return text[:width-1] + '…'

def capitalize(text: str) -> str:
    return text[0].upper() + text[1:]

class Project:
    def __init__(self, project_id: str, slug: str, project_type: str, name: str, author: str, description: str,
    downloads: int, follows: int, categories: list[str]):
        self.project_id: str = project_id
        self.slug: str = slug
        self.project_type: str = project_type
        self.name: str = name
        self.author: str = author
        self.description: str = description
        self.downloads: int = downloads
        self.follows: int = follows
        self.categories: list[str] = categories

        self.loaders: list[str] = list(filter(lambda category: category in LOADERS, self.categories))
        self.tags: list[str] = list(filter(lambda category: category not in LOADERS, self.categories))

    def __repr__(self) -> str:
        out: str = f'Project({repr(self.project_id)}, {repr(self.slug)}, {repr(self.project_type)}, {repr(self.name)}, '
        out += f'{repr(self.author)}, {repr(self.description)}, {self.downloads}, {self.follows}, {repr(self.categories)})'
        return out

    def __str__(self) -> str:
        out: str = f'{truncate(self.project_id, 8)}'
        out += f' {truncate(capitalize(self.project_type), 12)}' # Project type
        out += f' {truncate(self.name, 30)}' # Name
        out += f' {truncate(self.author, 20)}' # Author
        out += f' ⤓{truncate(f"{self.downloads:,}", 11)}' # Downloads
        out += f' ♥{truncate(f"{self.follows:,}", 7)}' # Follows
        out += f' {truncate(' '.join([capitalize(i) for i in self.loaders]), 50, False)}' # Loaders

        return out

    @staticmethod
    def from_json(data: dict) -> Project:
        return Project(data['project_id'], data['slug'], data['project_type'], data['title'], data['author'],
                       data['description'], data['downloads'], data['follows'], data['categories'])

class SearchResults:
    def __init__(self, projects: list[Project], page_number: int, page_count: int, total_hits: int, response_time: float):
        self.projects: list[Project] = projects
        self.page_number: int = page_number
        self.page_count: int = page_count
        self.total_hits: int = total_hits
        self.response_time: float = response_time

    def __repr__(self) -> str:
        return f'SearchResults([{len(self.projects)} projects], {self.page_number}, {self.page_count}, {self.total_hits}, {self.response_time})'

    def __str__(self) -> str:
        return f'{self.total_hits} results'

    def print(self) -> None:
        # Header
        print('ID       TYPE         NAME                           AUTHOR               DOWNLOADS    FOLLOWS  LOADERS')

        # Body
        for project in self.projects:
            print(project)

        # Footer
        print(f'Page {self.page_number+1}/{self.page_count} @ {PAGE_SIZE} items/page - {self.total_hits} results - Fetched in {int(self.response_time*1000):,}ms')

class SearchResultsError:
    def __init__(self, message: str):
        self.message: str = message

    def __repr__(self):
        return f'SearchResultsError({repr(self.message)})'

    def __str__(self):
        return f'Search error: {self.message}'

    def print(self) -> None:
        print(f'ERROR DURING SEARCH:\n')
        print(f'{"="*40}\n{self.message}{"="*40}')

def search(query: str = '', page_number: int = 0) -> SearchResults | SearchResultsError:
    # noinspection PyBroadException
    try:
        # Start timer
        start_time: float = time.time()

        # Separate search term from filters
        words: list[str] = query.split(' ')
        filters: list[str] = list(filter(lambda word: word.startswith('+') or word.startswith('-'), words))
        search_term: str = ' '.join(list(filter(lambda word: word not in filters, words)))

        # Parse search filters from query
        facets: list[list[str]] = []
        # TODO

        # Format URL
        offset: int = page_number * PAGE_SIZE
        url: str = f'https://api.modrinth.com/v2/search?query={search_term}&facets={json.dumps(facets)}&offset={offset}&limit={PAGE_SIZE}'

        # Send request and end timer
        r: requests.Response = requests.get(url)
        end_time: float = time.time()
        response_time: float = end_time - start_time
        data: dict = r.json()

        # Return results
        projects: list[Project] = [Project.from_json(hit) for hit in data['hits']]
        total_hits: int = data['total_hits']
        page_count: int = math.ceil(total_hits / PAGE_SIZE)
        results: SearchResults = SearchResults(projects, page_number, page_count, total_hits, response_time)
        return results

    except:
        return SearchResultsError(traceback.format_exc())

if __name__ == '__main__':
    # TEST
    search('').print()
