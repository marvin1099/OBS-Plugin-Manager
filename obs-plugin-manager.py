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

class OSManager: # Get corect read only values for the active os
    def __init__(self):
        self.system = platform.system()

    def data_base(self):
        if self.system == 'Windows':
            return os.getenv("APPDATA")
        elif self.system == 'Darwin':
            return os.path.expanduser("~/Library/Application Support")
        else:
            return os.path.expanduser("~/.config")

    @property
    def config_path(self):
        return os.path.join(self.data_base(), "obs-plugin-manager")

    @property
    def plugins_path(self):
        return os.path.join(self.data_base(), "obs-studio", "plugins")



class ConfigManager: # manage the config json files
    def __init__(self, config_path, plugins_path):
        self.config_path = config_path
        self.plugins_path = plugins_path
        self.config_file = "obs-plugin-manager.json"

        config = self.plugins_config
        self.user_plugins_path = config.get("user_plugins_path","")
        self.platforms_file_url = config.get("platforms_file_url","https://codeberg.org/marvin1099/OBS-Plugin-Manager/raw/branch/data/obs-plugin-platforms.json")
        self.platform_refresh_time = config.get("platform_refresh_time",86400)
        self.platform_cache_time = config.get("platform_cache_time",0)
        self.plugin_forum_url = config.get("plugin_forum_url","https://obsproject.com")
        self.plugin_forum_page_request = config.get("plugin_forum_page_request","/forum/plugins/?page=")
        self.plugin_soft_refresh_time = config.get("plugin_soft_refresh_time",86400)
        self.plugin_soft_cache_time = config.get("plugin_soft_cache_time",0)
        self.plugin_refresh_time = config.get("plugin_refresh_time",604800)
        self.plugin_cache_time = config.get("plugin_cache_time",0)

    @property
    def config_file(self):
        path = self._config_file
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self.config_path, path)

    @config_file.setter
    def config_file(self, file_path):
        if os.path.isabs(file_path):
            self._config_file = file_path
        else:
            self._config_file = os.path.join(self.config_path, file_path)

    @property
    def user_plugins_path(self):
        path = self._user_plugins_path
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self.plugins_path, path)

    @user_plugins_path.setter
    def user_plugins_path(self, path):
        if os.path.isabs(path):
            self._user_plugins_path = os.path.relpath(path, self.plugins_path)
        else:
            self._user_plugins_path = path
        self.plugins_config = {"user_plugins_path": self._user_plugins_path}

    @property
    def platforms_file_url(self):
        return self._platforms_file_url

    @platforms_file_url.setter
    def platforms_file_url(self, url):
        self._platforms_file_url = url
        self.plugins_config = {"platforms_file_url": url}

    @property
    def plugin_forum_url(self):
        return self._plugin_forum_url

    @plugin_forum_url.setter
    def plugin_forum_url(self, url):
        self._plugin_forum_url = url
        self.plugins_config = {"plugin_forum_url": url}

    @property
    def plugin_forum_page_request(self):
        return self._plugin_forum_page_request

    @plugin_forum_page_request.setter
    def plugin_forum_page_request(self, url):
        self._plugin_forum_page_request = url
        self.plugins_config = {"plugin_forum_page_request": url}

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

    @property # load
    def plugins_config(self):
        return self.load_json(self.config_file)

    @plugins_config.setter #save
    def plugins_config(self, data, loaded_file_priority=False):
        loaded_data = self.load_json(self.config_file)

        # if merge then loaded_data priority
        # when setting defaut merge will be true
        merged_data = self.merge_dicts(loaded_data, data, loaded_file_priority)

        self.save_json(self.config_file, merged_data)

    @plugins_config.deleter #delete
    def plugins_config(self, deletion_path=None):
        if deletion_path is None:
            # If no path is given, clear the entire config
            config = {}
        else:
            # Navigate through the dictionary to delete the specific path
            config = self.plugins_config
            current = config
            try:
                for key in deletion_path[:-1]:
                    current = current[key]

                del current[deletion_path[-1]]
            except Exception as e:
                print(f"Failed to delete path {deletion_path}: {e}")

        # Save the updated configuration
        self.save_json(self.config_file, config)

    @property
    def installed_plugins(self): # get list of plugins
        return self.plugins_config.get("plugins",{})

    @installed_plugins.setter
    def installed_plugins(self, data): # save to list of plugins
        self.plugins_config = {"plugins":data}

    @installed_plugins.deleter
    def installed_plugins(self, deletion_path=[]):
        deleter = self.__class__.plugins_config.fdel
        deleter(self, ["plugins"] + deletion_path)

    @property
    def platform_cache_time(self):
        return self._platform_cache_time

    @platform_cache_time.setter
    def platform_cache_time(self, unix_time):
        self._platform_cache_time = unix_time
        self.plugins_config = {"platform_cache_time":unix_time}

    @property
    def platforms(self):
        unix_time = int(time.time())
        div_time = unix_time - int(self.platform_cache_time)
        platforms_local = self.plugins_config.get("platforms_data",{})
        if div_time > self.platform_refresh_time:
            try:
                with request.urlopen(self.platforms_file_url) as response:
                    platforms_data = json.loads(response.read())
                    self.platform_cache_time = unix_time
                    self.platforms = platforms_data
                    return platforms_data
            except Exception as e:
                return platforms_local
        else:
            return platforms_local

    @platforms.setter
    def platforms(self, platform_data):
        self.plugins_config = {"platforms_data": data}

    @platforms.deleter
    def platforms(self, deletion_path=[]):
        deleter = self.__class__.plugins_config.fdel
        deleter(self, ["platforms_data"] + deletion_path)

    @property
    def plugin_cache_time(self):
        return self._plugin_cache_time

    @plugin_cache_time.setter
    def plugin_cache_time(self, unix_time):
        self._plugin_cache_time = unix_time
        self.plugins_config = {"plugin_cache_time":unix_time}

    @property
    def plugin_soft_cache_time(self):
        return self._plugin_soft_cache_time

    @plugin_soft_cache_time.setter
    def plugin_soft_cache_time(self, unix_time):
        self._plugin_soft_cache_time = unix_time
        self.plugins_config = {"plugin_soft_cache_time":unix_time}

    @property
    def online_cached_plugins(self): # get list of plugins
        return self.plugins_config.get("online_cached_plugins",{})

    @online_cached_plugins.setter
    def online_cached_plugins(self, data): # save to list of plugins
        self.plugins_config = {"online_cached_plugins":data}

    @online_cached_plugins.deleter
    def online_cached_plugins(self, deletion_path=[]):
        deleter = self.__class__.plugins_config.fdel
        deleter(self, ["online_cached_plugins"] + deletion_path)


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
        self.default_plugin["downloads"] = 0 # defaut to 0 for downloads # may remove in future

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
    def __init__(self, plugins_dict):
        pass

class OBSPluginManager:
    def __init__(self, CFM):
        self.CFM = CFM
        self.plugin_active_page = 1
        self.plugin_last_page = 1
        self.get_online_plugins()


    def get_online_plugins(self):
        unix_time = int(time.time())
        div_time = unix_time - int(self.CFM.plugin_cache_time)
        div_soft_time = unix_time - int(self.CFM.plugin_soft_cache_time)

        if div_soft_time > self.CFM.plugin_soft_refresh_time or div_time > self.CFM.plugin_refresh_time:
            if div_time > self.CFM.plugin_refresh_time:
                del self.CFM.online_cached_plugins
                self.CFM.online_cached_plugins = self.scrape_obs_plugins_all()
                self.CFM.plugin_cache_time = unix_time
            else:
                self.CFM.online_cached_plugins = self.scrape_obs_plugins()
            self.CFM.plugin_soft_cache_time = unix_time

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
        installed_plugins = self.CFM.installed_plugins
        if plugins is None:
            plugin = installed_plugins
        online_plugins = self.CFM.online_cached_plugins
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
                print(f"Remove plugin with id {plugin_id} {installed_data} here")
            elif online_data:
                print(f"Install / Update plugin with id {plugin_id} {online_data} here")
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
        online_plugins = self.CFM.online_cached_plugins
        to_install = self.match_plugin_querys(online_plugins, querys)
        self.plugin_actions_from_data(to_install)

    def remove_plugins(self, querys):
        installed_plugins = self.CFM.installed_plugins
        to_remove = self.match_plugin_querys(installed_plugins, querys)
        self.plugin_actions_from_data(to_remove,True)

    def query_plugins(self, querys, number_query, sort):
        online_plugins = self.CFM.online_cached_plugins
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
    CFM = ConfigManager(OSM.config_path, OSM.plugins_path)

    parser = argparse.ArgumentParser(
        prog='obs-plugin-manager.py',
        description='A OBS plugin manager, finder and downloader',
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
    parser.add_argument('-c', '--config', default=None, help=f'Config file to use (currently: "{CFM.config_file}")')

    args = parser.parse_args()

    if args.config:
        CFM.config_file = arg.config

    plugin_args = any([args.query, args.install, args.remove, args.update, args.number_filter])
    action_args = plugin_args or any([args.platform_url])

    if not action_args or args.help: # if no args are set or help is used
        parser.print_help() # print help
        if not action_args: #if no args are set exit
            exit(0)

    if args.platform_url:
        CFM.platforms_file_url = args.platform_url

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

