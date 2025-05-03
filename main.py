from __future__ import annotations
from typing import Callable, Any
from datetime import datetime
import traceback
import platform
import shutil
import json
import math
import time
import sys
import os

try:
    import requests
except ModuleNotFoundError:
    print('REQUESTS MODULE NOT FOUND')
    print('Please run "python.exe -m pip install requests" to fix this.')
    print('')
    input('Press ENTER to quit.')
    sys.exit()

# QUERY FORMAT
#
# Write your search string normally. For search filters, add a word that begins with "+" or "-"
# to filter for or against an attribute. Attributes are split into groups called "facets".
#
# FACETS
#
# Project Type
#     "mod", "resourcepack" OR "rp", "datapack" OR "dp", "modpack" OR "mp", "plugin", "shader"
#     NOTE: Project Types cannot be excluded with "-"
# Loader
#     Examples: "forge", "fabric", "neoforge", "quilt", "paper", "iris"
#     NOTE: Loaders cannot be excluded with "-"
# Platform
#     "server", "client", "serversupported", "clientsupported"
# Version
#     Use the letter "v" and then the Minecraft version. Examples: "v1.20.1", "v23w14a_or_b"
#     NOTE: Versions cannot be excluded with "-"
# Tag
#     Use the letter "t" and then the tag. Examples: "tsocial", "tadventure", "tcursed", "t16x"
#
# The search will return projects that match ANY of the "+" attributes AND NONE of the "-" attributes
# for EACH FACET.
#
# SORTING
#
# Add a word starting with "/" to sort with that rule in descending order.
# Valid rules: "relevance" (default), "downloads", "follows", "newest", "updated"
#
# EXAMPLES
#
# The filters "+forge +mod +rp -dp -mp -quilt" will return projects that meet the following:
# is a mod OR a resourcepack, AND is not a datapack NOR a modpack, AND is for Forge, AND is not for Quilt.
# Note that "+mod", "+rp", "-dp", and "-mp" get lumped together because they are all part of the "Project
# Type" facet. "+forge" and "-quilt" also are in their own "Loader" facet and so get handled separately.
#
# The query "trajectory -serversupported +neoforge +mod +v1.21.1 /follows" will search for NeoForge mods for 1.21.1
# that do not support a server version with the word "trajectory", and will sort by follows in descending order.
#
# The query "teleport +server" will search for projects that support a server-side version with the
# word "teleport", and will sort by relevance (default).

# CONSTANTS

SEARCH_URL: str = 'https://api.modrinth.com/v2/search'
VERSIONS_URL: str = 'https://api.modrinth.com/v2/project/{project_id}/version'
PAGE_SIZE: int = 20
VERSIONS_PAGE_SIZE: int = 15
RECOMMENDED_TERMINAL_SIZE: tuple[int, int] = (140, 40)
OUTPUT_DIRECTORY: str = 'downloads'
LOADING_ANIMATION: list[str] = ['-', '\\', '|', '/']

LOADERS: list[str] = ['bukkit', 'bungeecord', 'canvas', 'fabric', 'folia', 'forge', 'iris', 'liteloader', 'modloader',
                      'neoforge', 'optifine', 'paper', 'purpur', 'quilt', 'rift', 'spigot', 'sponge', 'vanilla', # "vanilla" is a loader for shaders
                      'velocity', 'waterfall']
SORTING_RULES: list[str] = ['relevance', 'downloads', 'follows', 'newest', 'updated']
ATTRIBUTES: dict[str, str] = {
    '+mod': 'project_type:mod',
    '+resourcepack': 'project_type:resourcepack',
    '+rp': 'project_type:resourcepack',
    '+datapack': 'project_type:datapack',
    '+dp': 'project_type:datapack',
    '+modpack': 'project_type:modpack',
    '+mp': 'project_type:modpack',
    '+plugin': 'project_type:plugin',
    '+shader': 'project_type:shader',
    **{f'+{loader}': f'categories:{loader}' for loader in LOADERS},
    '+server': 'client_side!=required',
    '-server': 'client_side:required',
    '+client': 'server_side!=required',
    '-client': 'server_side:required',
    # '+serverside': 'client_side!=required',
    # '-serverside': 'client_side:required',
    # '+clientside': 'server_side!=required',
    # '-clientside': 'server_side:required',
    '+serversupported': 'server_side!=unsupported',
    '-serversupported': 'server_side:unsupported',
    '+clientsupported': 'client_side!=unsupported',
    '-clientsupported': 'client_side:unsupported'
}
SPECIAL_ATTRIBUTES: dict[str, Callable[[str], str]] = {
    '+v': lambda version: f'versions:{version}',
    '+t': lambda tag: f'categories:{tag}',
    '-t': lambda tag: f'categories!={tag}'
}
FACETS: list[list[str]] = [
    ['mod', 'resourcepack', 'rp', 'datapack', 'dp', 'modpack', 'mp', 'plugin', 'shader'],
    LOADERS,
    ['server', 'client', 'serverside', 'clientside', 'serversupported', 'clientsupported'],
    ['v'],
    ['t']
]
SEARCH_EXPLANATION: str = '''
------ Search Filters ------
To add search filters, type a word beginning with "+" in your search term.
Some filters can also use "-" to search for projects that don't match the filter.

---- Search Filter List ----
Project Type: +mod, +resourcepack, +rp, +datapack, +dp, +modpack, +mp, +plugin, +shader
Loader: ''' + ', '.join([f'+{i}' for i in LOADERS]) + '''
Platform: +/-server, +/-client, +/-serversupported, +/-clientsupported
Version: +v<version> (Examples: +v1.12.2, +v1.16.5, +v1.21, +v25w14craftmine)
Tag: +/-t<version> (Examples: +tadventure, +ttechnology, -tcursed, -t32x)

------- Sorting Rule -------
To change the sorting rule, type a word beginning with "/" in your search term.
Valid rules: /relevance (default), /downloads, /follows, /newest, /updated
'''

# CLASS & FUNCTION DEFINITIONS

def truncate(text: str, width: int = 20, add_whitespace: bool = True) -> str:
    if len(text) <= width:
        if add_whitespace:
            return text.ljust(width)
        return text
    return text[:width-1] + '…'

def capitalize(text: str) -> str:
    return text[0].upper() + text[1:]

def get_facet_index(search_filter: str) -> int:
    for i in range(len(FACETS)):
        facet: list[str] = FACETS[i]
        if search_filter[1:] in facet:
            return i
        if search_filter[1] in facet: # special attributes only check for first letter
            return i
    raise ValueError(f'Internal Error: Invalid search filter "{search_filter}"!')

def clear_screen() -> None:
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

def format_file_size(size: int) -> str:
    units: list[int] = [1024 ** i for i in range(5)]
    unit_names: list[str] = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    for i in range(len(units)):
        if size < units[i] * 1024:
            return f'{size/units[i]:.2f} {unit_names[i]}'
    return f'{size//units[-1]:,} {unit_names[-1]}'

class Project:
    def __init__(self, project_id: str, slug: str, project_type: str, name: str, author: str, description: str,
    downloads: int, follows: int, categories: list[str], mc_versions: list[str], date_created: datetime,
    date_modified: datetime, project_license: str, client_support: str, server_support: str):
        self.project_id: str = project_id
        self.slug: str = slug
        self.project_type: str = project_type
        self.name: str = name
        self.author: str = author
        self.description: str = description
        self.downloads: int = downloads
        self.follows: int = follows
        self.categories: list[str] = categories
        self.mc_versions: list[str] = mc_versions
        self.date_created: datetime = date_created
        self.date_modified: datetime = date_modified
        self.project_license: str = project_license
        self.client_support: str = client_support
        self.server_support: str = server_support

        self.loaders: list[str] = list(filter(lambda category: category in LOADERS, self.categories))
        self.tags: list[str] = list(filter(lambda category: category not in LOADERS, self.categories))

    def __repr__(self) -> str:
        out: str = f'Project({repr(self.project_id)}, {repr(self.slug)}, {repr(self.project_type)}, {repr(self.name)}, …)'
        return out

    def __str__(self) -> str:
        out: str = truncate(self.project_id, 8) # Project ID
        out += f' {truncate(self.name, 30)}' # Name
        out += f' {truncate(capitalize(self.project_type), 12)}' # Project type
        out += f' {truncate(self.author, 20)}' # Author
        out += f' ⤓{truncate(f"{self.downloads:,}", 11)}' # Downloads
        out += f' ♥{truncate(f"{self.follows:,}", 7)}' # Follows
        out += f' {truncate(' '.join([capitalize(i) for i in self.loaders]), 50, False)}' # Loaders

        return out

    def print(self) -> None:
        print(f'"{self.name}" ({self.project_type}) by {self.author}    ⤓{self.downloads:,} ♥{self.follows:,}')
        print(self.description)
        print('')
        print(f'ID, Slug: {self.project_id}, {self.slug}')
        print(f'URL: https://modrinth.com/{self.project_type}/{self.project_id}')
        print(f'Date Created, Modified: {self.date_created.ctime()}, {self.date_modified.ctime()}')
        print(f'Client, Server Support: {self.client_support}, {self.server_support}')
        print(f'License: {self.project_license}')
        print('Loaders: ' + ' '.join([capitalize(i) for i in self.loaders]))
        print('Tags: ' + ' '.join([capitalize(i) for i in self.tags]))
        print('MC Versions: ' + ' '.join(list(reversed(self.mc_versions))[:10]) + ('…' if len(self.mc_versions) > 10 else ''))

    @staticmethod
    def from_json(data: dict) -> Project:
        return Project(data['project_id'], data['slug'], data['project_type'], data['title'], data['author'],
                       data['description'], data['downloads'], data['follows'], data['categories'], data['versions'],
                       datetime.fromisoformat(data['date_created']), datetime.fromisoformat(data['date_modified']),
                       data['license'], data['client_side'], data['server_side'])

class Version:
    def __init__(self, version_id: str, version_type: str, version_number: str, name: str, downloads: int,
                 mc_versions: list[str], loaders: list[str], files: list[VersionFile], dependency_ids: list[str],
                 project_id: str):
        self.version_id: str = version_id
        self.version_type: str = version_type
        self.version_level: int = {'alpha': 0, 'beta': 1, 'release': 2}[version_type]
        self.version_number: str = version_number
        self.name: str = name
        self.downloads: int = downloads
        self.mc_versions: list[str] = mc_versions
        self.loaders: list[str] = loaders
        self.files: list[VersionFile] = files
        self.dependency_ids: list[str] = dependency_ids
        self.dependencies: list[Project] | None = None # call get_dependency_info to get this value
        self.project_id: str = project_id

        # Move primary file to start of file list
        primary_file_index: int = 0
        for i in range(len(self.files)):
            if self.files[i].primary:
                primary_file_index = i
                break

        if primary_file_index != 0:
            self.files[0], self.files[primary_file_index] = self.files[primary_file_index], self.files[0]

        self.primary_file: VersionFile = self.files[0]

    def __repr__(self) -> str:
        return f'Version({repr(self.version_id)}, {repr(self.version_type)}, {repr(self.version_number)}, {repr(self.name)}, …)'

    def __str__(self) -> str:
        out: str = truncate(self.version_id, 8) # Version ID
        out += f' {truncate(self.version_type, 7)}' # Version type
        out += f' {truncate(self.version_number, 30)}' # Version number
        out += f' {truncate(format_file_size(self.primary_file.size), 11)}'
        out += f' ⤓{truncate(f"{self.downloads:,}", 10)}' # Downloads
        out += f' {truncate(' '.join([capitalize(i) for i in self.mc_versions]), 30)}' # MC Versions
        out += f' {truncate(' '.join([capitalize(i) for i in self.loaders]), 40, False)}' # Loaders

        return out

    def get_dependency_info(self) -> list[Project]:
        self.dependencies = []
        for dependency_id in self.dependency_ids:
            facets_param: list[list[str]] = [[f'project_id:{dependency_id}']]
            r: requests.Response = requests.get(SEARCH_URL, params={'facets': json.dumps(facets_param)})
            r.raise_for_status()
            data: dict = r.json()
            self.dependencies.append(Project.from_json(data['hits'][0]))
        return self.dependencies

    @staticmethod
    def from_json(data: dict) -> Version:
        return Version(data['id'], data['version_type'], data['version_number'], data['name'], data['downloads'],
                       data['game_versions'], data['loaders'],
                       [VersionFile.from_json(i) for i in data['files']],
                       [i['project_id'] for i in data['dependencies'] if i['dependency_type'] == 'required'],
                       data['project_id'])

class VersionFile:
    def __init__(self, url: str, filename: str, size: int, primary: bool):
        self.url: str = url
        self.filename: str = os.path.split(filename)[-1]
        self.size: int = size
        self.primary: bool = primary

    def __repr__(self) -> str:
        return f'VersionFile({repr(self.url)}, {repr(self.filename)}, {repr(self.size)}, {repr(self.primary)}'

    def __str__(self) -> str:
        return self.filename

    @staticmethod
    def from_json(data: dict) -> VersionFile:
        return VersionFile(data['url'], data['filename'], data['size'], data['primary'])

class SearchResults:
    def __init__(self, projects: list[Project], page_number: int, page_count: int, total_hits: int, response_time: float,
                 query: str):
        self.projects: list[Project] = projects
        self.page_number: int = page_number
        self.page_count: int = page_count
        self.total_hits: int = total_hits
        self.response_time: float = response_time
        self.query: str = query

    def __repr__(self) -> str:
        return f'SearchResults([{len(self.projects)} projects], {self.page_number}, {self.page_count}, {self.total_hits}, {self.response_time}, {repr(self.query)})'

    def __str__(self) -> str:
        return f'{self.total_hits} results'

    def print(self) -> None:
        # Header
        print(f'Query: "{self.query}"')
        print('')
        print('[#]  ID       NAME                           TYPE         AUTHOR               DOWNLOADS    FOLLOWS  LOADERS')

        # Body
        for i in range(len(self.projects)):
            project: Project = self.projects[i]
            print(f'{truncate("["+str(i)+"]", 4)} {project}')

        # Footer
        print(f'Page {self.page_number+1}/{self.page_count} @ {PAGE_SIZE} items/page - {self.total_hits} results - Fetched in {int(self.response_time*1000):,}ms')

class VersionsSearchResults:
    def __init__(self, versions: list[Version], page_number: int, page_count: int, total_hits: int, response_time: float,
                 project: Project):
        self.versions: list[Version] = versions
        self.page_number: int = page_number
        self.page_count: int = page_count
        self.total_hits: int = total_hits
        self.response_time: float = response_time
        self.project: Project = project

    def __repr__(self) -> str:
        return f'VersionsSearchResults([{len(self.versions)} versions], {self.page_number}, {self.page_count}, {self.total_hits}, {self.response_time}, {repr(self.project)})'

    def __str__(self) -> str:
        return f'{self.total_hits} versions'

    def start_index(self) -> int:
        return self.page_number * VERSIONS_PAGE_SIZE

    def end_index(self) -> int:
        return min(len(self.versions), (self.page_number + 1) * VERSIONS_PAGE_SIZE)

    def print(self) -> None:
        # Header
        print('[#]  ID       TYPE    VERSION                        SIZE        DOWNLOADS   MC VERSIONS                    LOADERS')

        # Body
        j: int = 0
        for i in range(self.start_index(), self.end_index()):
            version: Version = self.versions[i]
            print(f'{truncate("["+str(j)+"]", 4)} {version}')
            j += 1

        # Footer
        print(f'Page {self.page_number+1}/{self.page_count} @ {VERSIONS_PAGE_SIZE} items/page - {self.total_hits} results - Fetched in {int(self.response_time*1000):,}ms')

class SearchResultsError:
    def __init__(self, message: str):
        self.message: str = message

    def __repr__(self):
        return f'SearchResultsError({repr(self.message)})'

    def __str__(self):
        return f'Search error: {self.message}'

    def print(self) -> None:
        print(f'AN ERROR OCCURRED:\n')
        print(f'{"="*40}\n{self.message}{"="*40}')

def search(query: str = '', page_number: int = 0) -> SearchResults | SearchResultsError:
    # noinspection PyBroadException
    try:
        # Start timer
        start_time: float = time.time()

        # Separate search term from filters
        words: list[str] = query.split(' ')
        filters: list[str] = list(filter(lambda word: word.startswith('+') or word.startswith('-'), words))
        sorting_rules: list[str] = list(filter(lambda word: word.startswith('/'), words))
        search_term: str = ' '.join(list(filter(lambda word: (word not in filters) and (word not in sorting_rules), words)))

        # Parse sorting rule (if any)
        if len(sorting_rules) > 1:
            return SearchResultsError('More than 1 sorting rule found!\n')
        sorting_rule: str | None = None
        if len(sorting_rules) > 0:
            sorting_rule = sorting_rules[0][1:]
            if sorting_rule not in SORTING_RULES:
                return SearchResultsError(f'Invalid sorting rule "{sorting_rule}"!\nValid rules: {", ".join(SORTING_RULES)}\n')

        # Parse search filters (see "facets" parameter in Modrinth API docs for more info: https://docs.modrinth.com/api/operations/searchprojects/)
        facets_formatted: list[list[str]] = []
        for _ in range(len(FACETS)):
            facets_formatted.append([]) # Start with an empty OR expression for each facet

        for search_filter in filters: # For each search filter
            if search_filter in ATTRIBUTES: # If it is a normal attribute
                attribute_formatted: str = ATTRIBUTES[search_filter] # Find the formatted version of the attribute

            else:
                for special_attribute in SPECIAL_ATTRIBUTES:
                    if search_filter.startswith(special_attribute): # If it is a special attribute
                        attribute_formatted: str = SPECIAL_ATTRIBUTES[special_attribute](search_filter[2:]) # Apply special attribute function to find formatted version of the attribute
                        break

                else: # If it is not a valid attribute
                    return SearchResultsError(f'Invalid search filter "{search_filter}"!\n')

            # At this point, the attribute is valid and the formatted version has been found.
            facet_index: int = get_facet_index(search_filter) # Find the facet that the attribute belongs to
            if search_filter.startswith('+'):  # If it is a positive attribute
                facets_formatted[facet_index].append(attribute_formatted) # OR it with the other positive attributes of its facet
            else: # If it is a negative attribute
                facets_formatted.append([attribute_formatted]) # AND it with everything else

        facets_formatted = list(filter(lambda facet_formatted: len(facet_formatted) > 0, facets_formatted)) # Remove empty facets

        # Format URL parameters
        offset: int = page_number * PAGE_SIZE
        params: dict[str, str] = {'query': search_term, 'offset': offset, 'limit': PAGE_SIZE}
        if sorting_rule is not None:
            params['index'] = sorting_rule
        if len(facets_formatted) > 0:
            params['facets'] = json.dumps(facets_formatted)

        # Send request and end timer
        r: requests.Response = requests.get(SEARCH_URL, params=params)
        end_time: float = time.time()
        response_time: float = end_time - start_time
        data: dict = r.json()

        # Check for error response
        if 'error' in data:
            return SearchResultsError(f'Error on server:\n{data["error"]}: {data["description"]}\n')
        r.raise_for_status()

        # Return results
        projects: list[Project] = [Project.from_json(hit) for hit in data['hits']]
        total_hits: int = data['total_hits']
        page_count: int = max(1, math.ceil(total_hits / PAGE_SIZE))
        results: SearchResults = SearchResults(projects, page_number, page_count, total_hits, response_time, query)
        return results

    except:
        return SearchResultsError(traceback.format_exc())

def get_versions(project: Project) -> VersionsSearchResults | SearchResultsError:
    # noinspection PyBroadException
    try:
        # Start timer
        start_time: float = time.time()

        # Send request and end timer
        r: requests.Response = requests.get(VERSIONS_URL.format(project_id=project.project_id))
        r.raise_for_status()
        end_time: float = time.time()
        response_time: float = end_time - start_time
        data: list = r.json()

        # Return results
        versions: list[Version] = list(map(Version.from_json, data))
        total_hits: int = len(versions)
        page_count: int = max(1, math.ceil(total_hits / VERSIONS_PAGE_SIZE))
        versions_results: VersionsSearchResults = VersionsSearchResults(versions, 0, page_count, total_hits, response_time, project)
        return versions_results

    except:
        return SearchResultsError(traceback.format_exc())

# MAIN

if __name__ == '__main__':
    # Page types:
    # ['search']
    # ['results', <SearchResults object>]
    # ['error', <SearchResultsError object>, <page to return to>]
    # ['message', <text>]
    # ['project', <Project object>, <VersionsSearchResults object>, <SearchResults object>]
    # ['version', <Version object>, <page to return to>, <project slug>]
    # ['quit']
    page: list[Any] = ['search']

    # Mainloop
    while True:
        clear_screen()
        print('MODRINTH DOWNLOADER')
        print('-'*30)
        print('')
        terminal_size: os.terminal_size = shutil.get_terminal_size()

        new_search: tuple[str, int] | None = None

        # Search page
        if page[0] == 'search':
            print('SEARCH')
            print(SEARCH_EXPLANATION)
            print('')
            if terminal_size.columns < RECOMMENDED_TERMINAL_SIZE[0] or terminal_size.lines < RECOMMENDED_TERMINAL_SIZE[1]:
                print(f'! WARNING: A terminal size of at least {RECOMMENDED_TERMINAL_SIZE[0]}x{RECOMMENDED_TERMINAL_SIZE[1]} is recommended. Current size: {terminal_size.columns}x{terminal_size.lines}')
                print('')
            print('Enter search term (or "Q" to quit).')
            query: str = input(' > ')
            if query.lower() == 'q':
                page = ['quit']
            else:
                print('')
                new_search = (query, 0)

        # Results page
        elif page[0] == 'results':
            print('SEARCH RESULTS')
            print('')
            page[1].print()
            print('')
            print('Enter a number to view/download that project number.')
            print('Enter "<" or ">" to change page, or "p<number>" to jump to a page.')
            print('Enter "Q" to go back to search.')
            action = input(' > ')
            print('')

            # Quit
            if action.lower() == 'q':
                page = ['search']

            # Previous page
            elif action == '<':
                new_search = (page[1].query, (page[1].page_number - 1) % page[1].page_count)

            # Next page
            elif action == '>':
                new_search = (page[1].query, (page[1].page_number + 1) % page[1].page_count)

            # Jump to page
            elif action.lower().startswith('p'):
                try:
                    page_number: int = int(action[1:])
                except ValueError:
                    page = ['error', SearchResultsError(f'Invalid action "{action}"!\n'), page]
                else:
                    new_search = (page[1].query, (page_number - 1) % page[1].page_count)

            # View/download project
            else:
                try:
                    project_index: int = int(action)
                except ValueError:
                    page = ['error', SearchResultsError(f'Invalid action "{action}"!\n'), page]
                else:
                    if project_index < 0 or project_index >= len(page[1].projects):
                        page = ['error', SearchResultsError(f'Project index "{action}" out of bounds!\n'), page]
                    else:
                        project: Project = page[1].projects[project_index]
                        print('Getting versions...')
                        versions_results: VersionsSearchResults | SearchResultsError = get_versions(project)
                        if isinstance(versions_results, VersionsSearchResults):
                            page = ['project', project, versions_results, page[1]]
                        else:
                            page = ['error', versions_results, page]

        # Error page
        elif page[0] == 'error':
            page[1].print()
            print('')
            input('Press ENTER to go back.')
            page = page[2]

        # Message page (static page)
        elif page[0] == 'message':
            print(page[1])
            print('')
            input('Press ENTER to go back.')
            page = page[2]

        # Project page
        elif page[0] == 'project':
            page[1].print()
            print('')
            print('VERSIONS')
            page[2].print()
            print('')
            print('Enter a number to download that version.')
            print('Enter "<" or ">" to change page, or "p<number>" to jump to a page.')
            print('Enter something like "v1.21.1", "fabric", or "v1.21.1 fabric" to quick-download the latest matching version.')
            print('Enter "Q" to go back to search results.')
            action: str = input(' > ')

            # Check if action is quick download and parse if it is
            action_is_quick_download: bool = True
            version_filter: str | None = None
            loader_filter: str | None = None
            words: list[str] = action.split(' ')
            for word in words:
                if word.lower().startswith('v'):
                    if version_filter is not None:
                        action_is_quick_download = False
                        break
                    version_filter = word.lower()[1:]
                elif word.lower() in LOADERS:
                    if loader_filter is not None:
                        action_is_quick_download = False
                        break
                    loader_filter = word.lower()
                else:
                    action_is_quick_download = False
                    break
            if version_filter is None and loader_filter is None:
                action_is_quick_download = False

            # Quit
            if action.lower() == 'q':
                page = ['results', page[3]]

            # Previous page
            elif action == '<':
                page[2].page_number = (page[2].page_number - 1) % page[2].page_count

            # Next page
            elif action == '>':
                page[2].page_number = (page[2].page_number + 1) % page[2].page_count

            # Jump to page
            elif action.lower().startswith('p'):
                try:
                    page_number: int = int(action[1:])
                except ValueError:
                    page = ['error', SearchResultsError(f'Invalid action "{action}"!\n'), page]
                else:
                    page[2].page_number = (page_number - 1) % page[2].page_count

            # Quick-download version
            elif action_is_quick_download:
                match: Version | None = None
                for version in page[2].versions:
                    matches_version: bool = True
                    matches_loader: bool = True
                    if version_filter is not None:
                        if version_filter not in version.mc_versions:
                            matches_version = False
                    if loader_filter is not None:
                        if loader_filter not in version.loaders:
                            matches_loader = False
                    if matches_version and matches_loader:
                        if version.version_level > match.version_level:
                            match = version
                if match is None:
                    page = ['message', f'No versions matching "{action}" were found.', page]
                else:
                    page = ['version', match, page, page[1].slug]

            # Download version by index
            else:
                try:
                    version_index: int = int(action)
                except ValueError:
                    page = ['error', SearchResultsError(f'Invalid action "{action}"!\n'), page]
                else:
                    if version_index < 0 or version_index >= page[2].end_index() - page[2].start_index():
                        page = ['error', SearchResultsError(f'Version index "{action}" out of bounds!\n'), page]
                    else:
                        version: Version = page[2].versions[page[2].start_index() + version_index]
                        page = ['version', version, page, page[1].slug]

        # Version page (download page)
        elif page[0] == 'version':
            print('DOWNLOAD')
            print('')
            print(f'Type: {page[1].version_type}')
            print(f'Version: {page[1].version_number}')
            print(f'Version ID: {page[1].version_id}')
            print(f'Project ID: {page[1].project_id}')
            print(f'URL: https://modrinth.com/mod/{page[1].project_id}/version/{page[1].version_id}')
            if len(page[1].dependency_ids) == 0:
                print('Dependencies: none')
            else:
                print('Dependencies: loading...', end='\r')
                # noinspection PyBroadException
                try:
                    page[1].get_dependency_info()
                except:
                    page = ['error', SearchResultsError(traceback.format_exc()), page[2]]
                    continue # skips to error screen
                print('Dependencies: ' + ', '.join([f'"{i.name}" ({i.project_id})' for i in page[1].dependencies]))
            print('')
            print('FILES')
            print('')
            print('  FILENAME                                           SIZE')
            total_size: int = 0
            for file in page[1].files:
                primary_star: str = '*' if file.primary else ' '
                print(f'{primary_star} {truncate(file.filename, 50)} {format_file_size(file.size)}')
                total_size += file.size
            print('')
            print(f'Total size: {format_file_size(total_size)}')
            print('')
            print('Enter nothing to download the primary file.')
            print('Enter "A" to download all files.')
            print('Enter "Q" to cancel download.')
            action: str = input(' > ')
            print('')

            directory: str = os.path.join(OUTPUT_DIRECTORY, page[3]) # downloads/<project slug>
            warnings: str = ''
            if len(page[1].dependency_ids) > 0:
                warnings += '! THIS PROJECT HAS DEPENDENCIES! Make sure you get those as well.\n'
            if page[1].version_type == 'beta':
                warnings += '! THIS VERSION IS IN BETA!\n'
            if page[1].version_type == 'alpha':
                warnings += '! THIS VERSION IS IN ALPHA!\n'
            if warnings != '':
                warnings += '\n'

            # Download primary file
            if action == '':
                # noinspection PyBroadException
                try:
                    os.makedirs(directory, exist_ok=True)
                    local_filename: str = os.path.join(directory, page[1].primary_file.filename)
                    print('Downloading... ', end='\r')
                    loading_animation_frame: int = 0
                    downloaded_bytes: int = 0
                    with requests.get(page[1].primary_file.url, stream=True) as r:
                        r.raise_for_status()
                        with open(local_filename, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                print(f'Downloading... {LOADING_ANIMATION[loading_animation_frame]} {format_file_size(downloaded_bytes)}/{format_file_size(page[1].primary_file.size)}     ', end='\r')
                                f.write(chunk)
                                downloaded_bytes += 8192
                                loading_animation_frame = (loading_animation_frame + 1) % len(LOADING_ANIMATION)
                    print('Downloading... done                                        ')
                    print(f'Saved to "{local_filename}".')
                    print('')
                    print(warnings, end='')
                    input('Press ENTER to go back.')
                    page = page[2]

                except:
                    page = ['error', SearchResultsError(traceback.format_exc()), page[2]]

            # Download all files
            elif action.lower() == 'a':
                # noinspection PyBroadException
                try:
                    os.makedirs(directory, exist_ok=True)
                    print('Downloading... ', end='\r')
                    loading_animation_frame: int = 0
                    downloaded_bytes: int = 0
                    for file in page[1].files:
                        local_filename: str = os.path.join(directory, file.filename)
                        with requests.get(page[1].primary_file.url, stream=True) as r:
                            r.raise_for_status()
                            with open(local_filename, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    print(f'Downloading... {LOADING_ANIMATION[loading_animation_frame]} {format_file_size(downloaded_bytes)}/{format_file_size(total_size)}     ', end='\r')
                                    f.write(chunk)
                                    downloaded_bytes += 8192
                                    loading_animation_frame = (loading_animation_frame + 1) % len(LOADING_ANIMATION)
                    print('Downloading... done                                        ')
                    print(f'Saved files to "{directory}".')
                    print('')
                    print(warnings, end='')
                    input('Press ENTER to go back.')
                    page = page[2]

                except:
                    page = ['error', SearchResultsError(traceback.format_exc()), page[2]]

            # Quit
            else:
                page = page[2]

        # Quit
        else:
            print('Goodbye')
            sys.exit()

        # Perform search
        if new_search is not None:
            print('Searching...')
            results: SearchResults | SearchResultsError = search(*new_search)
            if isinstance(results, SearchResults):
                page = ['results', results]
            else:
                page = ['error', results, ['search']]
