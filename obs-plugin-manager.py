#!/usr/bin/python
import os
import json
import time
import fnmatch
import platform
import argparse
from collections import OrderedDict
from html.parser import HTMLParser
from urllib import request

#CONFIG_DIR = os.path.expanduser("~/.config/obs-plugin-pm")
#PLUGINS_DIR = os.path.expanduser("~/.config/obs-studio/plugins/")
#INSTALLED_PLUGINS_FILE = os.path.join(CONFIG_DIR, "installed_plugins.json")

class OSManager: # Get corect values for the active os
    def __init__(self):
        self.system = platform.system()

    def data_base(self):
        if self.system == 'Windows':
            return os.getenv("APPDATA")
        elif self.system == 'Darwin':
            return os.path.expanduser("~/Library/Application Support")
        else:
            return os.path.expanduser("~/.config")

    def get_config_path(self):
        return os.path.join(self.data_base(), "obs-plugin-manager")

    def get_plugins_path(self):
        return os.path.join(self.data_base(), "obs-studio", "plugins")

class ConfigManager: # manage the config json files
    def __init__(self, config_path):
        self.config_path = config_path
        self.plugins_file = os.path.join(self.config_path, "obs-plugin-manager.json")
        self.save_plugins_config(
            {
                "platforms_file_url": "https://codeberg.org/marvin1099/OBS-Plugin-Manager/raw/branch/data/obs-plugin-platforms.json",
                "platform_refresh_time": 86400,
                "platform_cache_time": 0,
                "plugin_forum_url": "https://obsproject.com",
                "plugin_forum_page_request": "/forum/plugins/?page=",
                "plugin_soft_refresh_time": 86400,
                "plugin_soft_cache_time": 0,
                "plugin_refresh_time": 604800,
                "plugin_cache_time": 0,
            },
            loaded_file_priority=True
        )
        data = self.load_plugins_config()
        self.platforms_file_url = data["platforms_file_url"]
        self.platform_refresh_time = data["platform_refresh_time"]
        self.platform_cache_time = data["platform_cache_time"]
        self.plugin_forum_url = data["plugin_forum_url"]
        self.plugin_forum_page_request = data["plugin_forum_page_request"]
        self.plugin_soft_refresh_time = data["plugin_soft_refresh_time"]
        self.plugin_soft_cache_time = data["plugin_soft_cache_time"]
        self.plugin_refresh_time = data["plugin_refresh_time"]
        self.plugin_cache_time = data["plugin_cache_time"]

    def update_config_file(self, file_path):
        if os.path.isabs(file_path):
            self.plugins_file = file_path
        else:
            self.plugins_file = os.path.join(self.config_path, file_path)

    def update_platforms_file_url(self, url):
        self.plugin_forum_url = url
        self.save_plugins_config({"platforms_file_url": url})

    def update_plugin_forum_url(self, url):
        self.plugin_forum_url = url
        self.save_plugins_config({"plugin_forum_url": url})

    def update_plugin_forum_page_request(self, url):
        self.plugin_forum_page_request = url
        self.save_plugins_config({"plugin_forum_page_request": url})

    def load_json(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}

    def save_json(self, filepath, data):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def merge_dicts(self, d1, d2, first_priority=True):
        def merge_values(v1, v2):
            if isinstance(v1, dict) and isinstance(v2, dict):
                return self.merge_dicts(v1, v2, first_priority)
            elif isinstance(v1, list) and isinstance(v2, list):
                return merge_lists(v1, v2)
            else:
                return v1 if first_priority == True else v2

        def merge_lists(l1, l2):
            merged = []
            for item in l1:
                if item not in merged:
                    merged.append(item)
            for item in l2:
                if isinstance(item, dict):
                    found = False
                    for idx, existing_item in enumerate(merged):
                        if isinstance(existing_item, dict) and existing_item.keys() == item.keys():
                            merged[idx] = self.merge_dicts(existing_item, item, first_priority)
                            found = True
                            break
                    if not found:
                        merged.append(item)
                elif item not in merged:
                    merged.append(item)
            return merged

        merged = {}
        for key in set(d1) | set(d2):
            if key in d1 and key in d2:
                merged[key] = merge_values(d1[key], d2[key])
            elif key in d1:
                merged[key] = d1[key]
            else:
                merged[key] = d2[key]
        return merged

    def load_plugins_config(self):
        return self.load_json(self.plugins_file)

    def save_plugins_config(self, data, loaded_file_priority=False):
        loaded_data = self.load_json(self.plugins_file)

        # if merge then loaded_data priority
        # when setting defaut merge will be true
        merged_data = self.merge_dicts(loaded_data, data, loaded_file_priority)

        self.save_json(self.plugins_file, merged_data)

    def delete_plugins_config_entry(self, deletion_path):
        loaded_data = self.load_plugins_config()
        current = loaded_data

        try:
            for key in deletion_path[:-1]:
                current = current[key]

            del current[deletion_path[-1]]
        except (KeyError, IndexError, TypeError) as e:
            print(f"Failed to delete path {deletion_path}: {e}")
        else:
            self.save_json(self.plugins_file, loaded_data)

    def load_installed_plugins(self): # get list of plugins
        return self.load_plugins_config().get("plugins",{})

    def save_installed_plugins(self, data): # save to list of plugins
        self.save_plugins_config({"plugins":data})

    def delete_installed_plugins(self, deletion_path):
        self.delete_plugins_config_entry(["plugins"] + deletion_path)

    def update_platform_cache_time(self, unix_time):
        self.platform_cache_time = unix_time
        self.save_plugins_config({"platform_cache_time":unix_time})

    def load_platforms(self):
        unix_time = int(time.time())
        div_time = unix_time - int(self.platform_cache_time)
        platforms_local = self.load_plugins_config().get("platforms_data",{})
        if div_time > self.platform_refresh_time:
            try:
                with request.urlopen(self.platforms_file_url) as response:
                    platforms_data = json.loads(response.read())
                    self.save_platforms(platforms_data)
                    self.platform_cache_time = unix_time
                    self.update_plugin_cache_time(unix_time)
                    return platforms_data
            except Exception as e:
                return platforms_local
        else:
            return platforms_local

    def save_platforms(self, platform_data):
        self.save_plugins_config({"platforms_data": data})

    def delete_platforms(self, deletion_path=[]):
        self.delete_plugins_config_entry(["platforms_data"] + deletion_path)

    def update_plugin_cache_time(self, unix_time):
        self.plugin_cache_time = unix_time
        self.save_plugins_config({"plugin_cache_time":unix_time})

    def update_plugin_soft_cache_time(self, unix_time):
        self.plugin_soft_cache_time = unix_time
        self.save_plugins_config({"plugin_soft_cache_time":unix_time})

    def load_online_cached_plugins(self): # get list of plugins
        return self.load_plugins_config().get("online_cached_plugins",{})

    def save_online_cached_plugins(self, data): # save to list of plugins
        self.save_plugins_config({"online_cached_plugins":data})

    def delete_online_cached_plugins(self, deletion_path=[]):
        self.delete_plugins_config_entry(["online_cached_plugins"] + deletion_path)


class OBSPluginPageParser(HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.plugins = {}
        self.default_plugin = {
            'id': None,
            'author': None,
            'title': None,
            'description': None,
            'uploaded': None,
            'updated': None,
            'stars': None,
            'downloads': None,
            'url': None,
        }
        self.current_plugin = dict(self.default_plugin)
        self.url = url
        self.last_page = 1
        self.in_plugin_div = 0
        self.in_title_div = False
        self.in_downloads = False
        self.in_description = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'input' and 'class' in attrs_dict and 'js-pageJumpPage' in attrs_dict['class']:
            if 'max' in attrs_dict:
                self.last_page = int(attrs_dict['max'])

        if tag == 'div' and 'class' in attrs_dict:
            if 'structItem structItem--resource' in attrs_dict['class']:
                self.in_plugin_div = 1
                self.current_plugin['author'] = attrs_dict.get('data-author', '')
                self.current_plugin['id'] = attrs_dict.get('class').split("-")[-1]

        if self.in_plugin_div:
            if tag == 'div':
                self.in_plugin_div += 1

            if tag == 'a' and 'href' in attrs_dict and 'data-tp-primary' in attrs_dict:
                self.current_plugin['url'] = self.url + attrs_dict.get('href', '')
                self.in_title_div = True

            if tag == 'time' and 'class' in attrs_dict:
                unix_time = attrs_dict.get('data-time', '0')
                try:
                    unix_time = int(unix_time)
                except Exception as e:
                    pass
                else:
                    if self.current_plugin.get('uploaded') is None:
                        self.current_plugin['updated'] = unix_time
                        self.current_plugin['uploaded'] = unix_time
                    else:
                        self.current_plugin['updated'] = unix_time

            if tag == 'div' and 'class' in attrs_dict and "structItem-resourceTagLine" in attrs_dict['class']:
                self.in_description = True

            if tag == 'span' and 'class' in attrs_dict and "ratingStars--larger" in attrs_dict['class']:
                stars = ""
                try:
                    for char in attrs_dict['title']:
                        if char.isnumeric() or char == '.':
                            stars += char
                    stars = float(stars)
                except Exception as e:
                    pass
                else:
                    self.current_plugin['stars'] = stars

            if tag == 'dl' and 'class' in attrs_dict and "structItem-metaItem--downloads" in attrs_dict['class']:
                self.in_downloads = True


    def handle_endtag(self, tag):
        if self.in_plugin_div:
            if tag == 'div':
                self.in_plugin_div -= 1
                if self.in_plugin_div == 1:
                    plugin_id = self.current_plugin.get("id")
                    if plugin_id:
                        del self.current_plugin["id"]
                    self.plugins[plugin_id] = self.current_plugin
                    self.current_plugin = dict(self.default_plugin)
                    self.in_plugin_div = 0

            if tag == 'a' and self.in_title_div:
                self.in_title_div = False

            if tag == 'dl':
                self.in_downloads = False

    def handle_data(self, data):
        if self.in_plugin_div:
            if self.in_title_div:
                self.current_plugin['title'] = data.strip()

            if self.in_description:
                self.current_plugin['description'] = data.strip()
                self.in_description = False

            if self.in_downloads:
                download_data = data.strip()
                if download_data:
                    try:
                        download_data = int(download_data.replace(",","").replace(".",""))
                    except Exception as e:
                        pass
                    else:
                        self.current_plugin['downloads'] = download_data

    def error(self, message):
        print(str(message))


class OBSPluginDownloader:
    def __init__(self, platform, repo, plugin_name, download_dir, version_file, config):
        self.platform = platform
        self.repo = repo
        self.plugin_name = plugin_name
        self.download_dir = download_dir
        self.version_file = version_file
        self.config = config
        self.api_url = self.config[platform]['api_url'].format(repo=repo, plugin=plugin_name)
        self.file_pattern = self.config[platform]['file_pattern']

    def get_latest_release_info(self):
        response = requests.get(self.api_url)
        response.raise_for_status()
        releases = response.json()
        latest_release = next((release for release in releases if not release.get('prerelease', False)), None)
        return latest_release

    def get_current_version(self):
        if os.path.exists(self.version_file):
            with open(self.version_file, 'r') as f:
                return f.read().strip()
        return None

    def save_current_version(self, version):
        with open(self.version_file, 'w') as f:
            f.write(version)

    def download_asset(self, download_url, output_path):
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def update_plugin(self):
        latest_release = self.get_latest_release_info()
        if not latest_release:
            print("No releases found.")
            return

        latest_version = latest_release['tag_name']
        current_version = self.get_current_version()

        if current_version == latest_version:
            print(f"You already have the latest version ({current_version}) downloaded.")
            return

        for asset in latest_release['assets']:
            if fnmatch.fnmatch(asset['name'], self.file_pattern):
                download_url = asset['browser_download_url']
                output_path = os.path.join(self.download_dir, asset['name'])
                print(f"Downloading {asset['name']}...")
                self.download_asset(download_url, output_path)
                print(f"Downloaded to {output_path}")

        self.save_current_version(latest_version)
        print(f"Updated to version: {latest_version}")


class OBSPluginManager:
    def __init__(self, CFM):
        self.CFM = CFM
        self.plugin_active_page = 1
        self.plugin_last_page = 1
        self.get_online_plugins()


    def get_online_plugins(self):
        self.CFM.load_online_cached_plugins()

        unix_time = int(time.time())
        div_time = unix_time - int(self.CFM.plugin_cache_time)
        div_soft_time = unix_time - int(self.CFM.plugin_soft_cache_time)

        if div_soft_time > self.CFM.plugin_soft_refresh_time or div_time > self.CFM.plugin_refresh_time:
            if div_time > self.CFM.plugin_refresh_time:
                self.CFM.delete_online_cached_plugins()
                self.CFM.save_online_cached_plugins(self.scrape_obs_plugins_all())
                self.CFM.update_plugin_cache_time(unix_time)
            else:
                self.CFM.save_online_cached_plugins(self.scrape_obs_plugins())
            self.CFM.update_plugin_soft_cache_time(unix_time)

    def scrape_obs_plugins_all(self):
        plugins = {}
        while self.plugin_active_page <= self.plugin_last_page:
            plugins.update(self.scrape_obs_plugins())
            self.plugin_active_page += 1
        return plugins

    def scrape_obs_plugins(self):
        url = f"{self.CFM.plugin_forum_url}{self.CFM.plugin_forum_page_request}{self.plugin_active_page}"
        try:
            with request.urlopen(url) as response:
                print("Getting Plugin Page: " + str(self.plugin_active_page))
                html_content = response.read().decode('utf-8')
                parser = OBSPluginPageParser(CFM.plugin_forum_url)
                parser.feed(html_content)
                self.plugin_last_page = parser.last_page # update last page
                return parser.plugins
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return {}

    def plugin_actions_from_data(self, plugins=None, remove=False):
        installed_plugins = self.CFM.load_installed_plugins()
        if plugins is None:
            plugin = installed_plugins
        online_plugins = self.CFM.load_online_cached_plugins()
        for plugin_id, plugin in plugins.items():
            online_data = online_plugins.get(plugin_id,{})
            installed_data = installed_plugins.get(plugin_id,{})
            if plugin != online_data and plugin != installed_data:
                if any(key in plugin for key in ("downloads", "stars")):
                    plugin.update(online_data)
                    online_data = plugin
                else:
                    plugin.update(installed_data)
                    installed_data = plugin
            if remove and installed_data:
                print(f"Remove plugin with id {plugin_id} here")
            elif online_data:
                print(f"Install / Update plugin with id {plugin_id} here")
            # platform = plugin['platform']
            # repo = plugin['repo']
            # plugin_name = plugin['name']
            # version_file = os.path.join(self.plugins_dir, f"{plugin_name}_version.txt")
            # downloader = OBSPluginDownloader(platform, repo, plugin_name, self.plugins_dir, version_file, self.platforms)
            # downloader.update_plugin()

    def query_plugin_data(self, data, query):
        found_plugins = {}
        online_plugins = data
        for plugin_id, plugin_infos in online_plugins.items():
            for info_key, plugin_info in plugin_infos.items():
                if info_key == "url":
                    plugin_info = plugin_info.split("/")[-2]
                if isinstance(plugin_info, str) and query.lower() in plugin_info.lower():
                    found_plugins.update({plugin_id:plugin_infos})
                    break

        return found_plugins

    def exact_query_plugin_data(self, data, query):
        found_plugins = {}
        online_plugins = data
        special = None
        priority = {"id":6,"url":5,"name":4,"description":3,"title":2,"author":1}
        current_priority = 0
        for plugin_id, plugin_infos in online_plugins.items():
            for info_key, plugin_info in plugin_infos.items():
                if info_key == "url":
                    plugin_info = plugin_info.split("/")[-2]
                    special = plugin_info.split(".")
                    special = [".".join(special[:-1]), special[-1]]
                if isinstance(plugin_info, str):
                    if query.lower() == plugin_info.lower():
                        new_priority = priority.get(info_key,0)
                        if new_priority >= current_priority:
                            if new_priority > current_priority:
                                found_plugins = {}
                                current_priority = int(new_priority)
                            found_plugins.update({plugin_id:plugin_infos})
                    if special and query.lower() == special[0].lower():
                        new_priority = priority.get("name")
                        if new_priority >= current_priority:
                            if new_priority > current_priority:
                                found_plugins = {}
                                current_priority = int(new_priority)
                            found_plugins.update({plugin_id:plugin_infos})
                    if special and query.lower() == special[1].lower():
                        new_priority = priority.get("id")
                        if new_priority >= current_priority:
                            if new_priority > current_priority:
                                found_plugins = {}
                                current_priority = int(new_priority)
                            found_plugins.update({plugin_id:plugin_infos})
                special = None

        return found_plugins, current_priority



    def limit_number_query(self, data, querys):
        for query in querys:
            key = query[0]
            operator = query[1]
            try:
                number = float(query[2])
            except Exception as e:
                pass
            else:
                found = {}
                for plugin_id, plugin_infos in data.items():
                    for info_key, plugin_info in plugin_infos.items():
                        if info_key == key and isinstance(plugin_info, tuple([int, float])):
                            if operator == ">" and plugin_info > number:
                                found.update({plugin_id: plugin_infos})
                                break
                            if operator == "<" and plugin_info < number:
                                found.update({plugin_id: plugin_infos})
                                break
                            if operator == ">=" and plugin_info >= number:
                                found.update({plugin_id: plugin_infos})
                                break
                            if operator == "<=" and plugin_info <= number:
                                found.update({plugin_id: plugin_infos})
                                break
                            if operator == "!=" and plugin_info != number:
                                found.update({plugin_id: plugin_infos})
                                break
                            if operator == "==" and plugin_info == number:
                                found.update({plugin_id: plugin_infos})
                                break
                data = dict(found)

        return data


    def limit_plugin_querys(self,data,querys):
        for query in querys:
            data = self.query_plugin_data(data, query)

        return data

    def parse_number_conditions(self,condition_strings):
        conditions = []
        i = 0
        while i < len(condition_strings):
            if isinstance(condition_strings[i], str) and any(op in condition_strings[i] for op in ['>=', '<=', '==', '!=', '>', '<']):
                # If condition is in a combined format like "key>value"
                condition = condition_strings[i]
                if '>=' in condition:
                    key, value = condition.split('>=')
                    conditions.append([key.strip(), '>=', value.strip()])
                elif '<=' in condition:
                    key, value = condition.split('<=')
                    conditions.append([key.strip(), '<=', value.strip()])
                elif '==' in condition:
                    key, value = condition.split('==')
                    conditions.append([key.strip(), '==', value.strip()])
                elif '!=' in condition:
                    key, value = condition.split('!=')
                    conditions.append([key.strip(), '!=', value.strip()])
                elif '>' in condition:
                    key, value = condition.split('>')
                    conditions.append([key.strip(), '>', value.strip()])
                elif '<' in condition:
                    key, value = condition.split('<')
                    conditions.append([key.strip(), '<', value.strip()])
            else:
                # If condition is in a separated format like ["key", ">", "value"]
                key, operator, value = condition_strings[i:i+3]
                conditions.append([key.strip(), operator.strip(), value.strip()])
                i += 2  # Skip next two items
            i += 1
        return conditions


    def sort_dict_by_key(self, data, sort_key=None, reverse=False):
        if sort_key is None:
            sort_key = "updated"
        # Function to sort sub-dictionary keys
        def sort_sub_dict(sub_dict):
            return dict(sorted(sub_dict.items(), key=lambda item: item[0]))

        if sort_key == "id":
            # Sort by the dictionary keys (which are the IDs)
            sorted_data = OrderedDict(
                sorted(data.items(), key=lambda item: int(item[0]), reverse=reverse)
            )
        else:
            # Attempt to sort the dictionary by the specified key
            sorted_data = OrderedDict(
                sorted(data.items(), key=lambda item: item[1].get(sort_key, 0), reverse=reverse)
            )

        # Sort keys within each sub-dictionary
        for key in sorted_data:
            sorted_data[key] = sort_sub_dict(sorted_data[key])

        return dict(sorted_data)


    def plugins_print(self, data, top_nl=True):
        if top_nl:
            print("")
        for plugin_id, plugin_infos in data.items():
            print(f"--- Plugin id {plugin_id} ---")
            for info_key, plugin_info in plugin_infos.items():
                print(f"{info_key}: {plugin_info}")
                if info_key == "url" and isinstance(plugin_info, str):
                    print(f"{info_key}_title: {(["",""] + plugin_info.split("/"))[-2].split(".")[0]}")
            print("")

    def match_plugin_querys(self, data, querys):
        match_data = {}
        for query in querys:
            target_plugin = {}
            results, _ = self.exact_query_plugin_data(data, query)
            sorted_results = self.sort_dict_by_key(results,None)
            nr_results = len(sorted_results)
            if nr_results == 0:
                print(f"Nothing found for '{query}'")
            elif nr_results == 1:
                target_plugin = {list(sorted_results.keys())[0]:sorted_results[list(sorted_results.keys())[0]]}
                print(f"For '{query}' id {list(sorted_results.keys())[0]} was found")
            else:
                target_plugin = {list(sorted_results.keys())[-1]:sorted_results[list(sorted_results.keys())[-1]]}
                print(f"Multiple results found for '{query}', found ids are {', '.join(list(sorted_results.keys()))}")
                print(f"Returned for '{query}' will be the id {list(sorted_results.keys())[-1]}")
            if target_plugin:
                match_data.update(target_plugin)

        return match_data


    def download_plugins(self, querys):
        online_plugins = self.CFM.load_online_cached_plugins()
        to_install = self.match_plugin_querys(online_plugins, querys)
        self.plugin_actions_from_data(to_install)

    def remove_plugins(self, querys):
        installed_plugins = self.CFM.load_installed_plugins()
        to_remove = self.match_plugin_querys(installed_plugins, querys)
        self.plugin_actions_from_data(to_remove,True)

    def query_plugins(self, querys, number_query, sort):
        online_plugins = self.CFM.load_online_cached_plugins()
        if number_query:
            number_conditions = self.parse_number_conditions(number_query)
            online_plugins = self.limit_number_query(online_plugins, number_conditions)
        if querys:
            online_plugins = self.limit_plugin_querys(online_plugins, querys)
        sorted_plugins = self.sort_dict_by_key(online_plugins, sort)
        return sorted_plugins


    def update_installed_plugins(self):
        self.plugin_actions_from_data()


if __name__ == "__main__": # Run the steps
    OSM = OSManager()
    CFM = ConfigManager(OSM.get_config_path())

    parser = argparse.ArgumentParser(
        prog='obs-plugin-manager.py',
        description='A OBS plugin finder and downloader',
        add_help=False,
        epilog='')
    parser.add_argument('-h', '--help', action='store_true', help='show this help message and exit')
    parser.add_argument('-q', '--query', nargs="+", action='extend', default=[], help='search for an online database plugin')
    parser.add_argument('-n', '--number-filter', dest='number_filter', nargs="+", action='extend', default=[], help='search for number conditons eg: -n "stars>4" "downloads>1000"')
    parser.add_argument('-i', '--install', nargs="+", action='extend', default=[], help='install a online database plugin/s')
    parser.add_argument('-r', '--remove', nargs="+", action='extend', default=[], help='remove installed plugin/s')
    parser.add_argument('-u', '--update', action='store_true', help='update installed plugins')
    parser.add_argument('-s', '--sort', choices={"id","author","title","updated","uploaded","url","stars"}, help='sort the querry output by key')
    #parser.add_argument('-o', '--ols', action='store_true', help='list indexed online plugins')
    #parser.add_argument('-l', '--ls', action='store_true', help='list installed plugins')
    #parser.add_argument('-d', '--dignore', action='store_true', help='disable ignore list')
    #parser.add_argument('-g', '--ignoreurl', default='', help='set ignore url')
    parser.add_argument('-p', '--platform-url', dest='platform_url', default=None, help=f'set platform json url (currently: "{CFM.platforms_file_url}")')
    parser.add_argument('-c', '--config', default=None, help=f'Config file to use (currently: "{CFM.plugins_file}")')

    args = parser.parse_args()

    if args.config:
        CFM.update_config_file(arg.config)

    plugin_args = any([args.query, args.install, args.remove, args.update, args.number_filter])
    action_args = plugin_args or any([args.platform_url])

    if not action_args or args.help: # if no args are set or help is used
        parser.print_help() # print help
        if not any_args: #if no args are set exit
            exit(0)

    if args.platform_url:
        CFM.update_platforms_file_url(args.platform_url)

    if plugin_args: # if these args are set the plugin manager needs to run

        OPM = OBSPluginManager(CFM) # update online index if needed

        if args.query or args.number_filter:
            found = OPM.query_plugins(args.query, args.number_filter, args.sort)
            OPM.plugins_print(found)
            #pass # send command to search for plugin
            # here we use all the list items and
            # only return a result if all of terms are in the result

        if args.install:
            OPM.download_plugins(args.install)

        for plugin in args.remove:
            pass # send command to remove plugin here

        if args.update:
            OPM.update_installed_plugins() # send command to update all

