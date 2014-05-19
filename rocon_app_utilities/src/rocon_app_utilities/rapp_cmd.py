#!/usr/bin/env python
#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_app_platform/license/LICENSE
#
#################################################################################

from __future__ import division, print_function

import argparse
import os
import subprocess
import sys
import traceback
import yaml

import rospkg

from .dependencies import DependencyChecker
from .rapp_repositories import build_index, get_combined_index, get_index, get_index_dest_prefix_for_base_paths, is_index, load_uris, sanitize_uri, save_uris, uri2url

#################################################################################
# Global variables
#################################################################################

NAME = 'rocon_app'
RAPP_DEPS_CACHE_FILE = os.path.join(rospkg.get_ros_home(), 'rocon', 'rapp', 'rapp_deps_cache.yaml')

#################################################################################
# Local methods
#################################################################################

def _cache_rapp_deps(new_dep_rapp_dict):
    """
        Caches rapp dependencies installed by
    """

    base_path = os.path.dirname(RAPP_DEPS_CACHE_FILE)
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    if not os.path.isfile(RAPP_DEPS_CACHE_FILE):
        print("Could not find the specified install cache file [%s]" % RAPP_DEPS_CACHE_FILE)
        with open(os.path.abspath(RAPP_DEPS_CACHE_FILE), 'w') as f:
            empty_dic = {}
            yaml.dump(empty_dic, f)
            f.close()

    with open(os.path.abspath(RAPP_DEPS_CACHE_FILE), 'r') as f:
        rapp_deps_cache = yaml.load(f)

    if rapp_deps_cache:
        print("\nInstalled rapp dependency cache")
        for cache_dep, cache_rapps in rapp_deps_cache.items():
            print("  %s: %s" % (cache_dep, cache_rapps))
    else:
        print("\nInstalled rapp dependency cache is empty.")

    if new_dep_rapp_dict:
        if rapp_deps_cache:
            for cache_dep, cache_rapps in rapp_deps_cache.items():
                for new_rapp, new_deps in new_dep_rapp_dict.items():
                    for new_dep in new_deps:
                        if new_dep == cache_dep:
                            if not new_rapp in cache_rapps:
                                cache_rapps.append(new_rapp)
                                print("\nAdding new entries:")
                                print("  %s: %s" % (cache_dep, new_rapp))
                        else:
                            rapp_list.append(new_rapp)
                            new_dep_rapp[new_dep] = rapp_list
                            rapp_deps_cache.append(new_dep_rapp)
                            print("\nAdding new entries:")
                            print("  %s: %s" % (new_dep, new_rapp))
        else:
            rapp_deps_cache = {}
            for new_rapp, new_deps in new_dep_rapp_dict.items():
                for new_dep in new_deps:
                    if new_dep in rapp_deps_cache:
                        rapp_deps_cache[new_dep].append(new_rapp)
                    else:
                        rapp_list = []
                        rapp_list.append(new_rapp)
                        new_dep_rapp = {}
                        rapp_deps_cache[new_dep] = rapp_list
                    print("  %s: %s" % (new_dep, rapp_deps_cache[new_dep]))
    else:
        print("No new rapp dependencies provided.")

    print("\nUpdated Install Cache")
    for cache_dep, cache_rapps in rapp_deps_cache.items():
        print("  %s: %s" % (cache_dep, cache_rapps))

    print("\nDumping the Install cache to '%s'" % RAPP_DEPS_CACHE_FILE)
    with open(os.path.abspath(RAPP_DEPS_CACHE_FILE), 'w') as f:
        yaml.dump(rapp_deps_cache, f)

def _rapp_cmd_list(argv):
    """
      Command-line parsing for 'rapp list' command.
    """
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Displays rapp information')
    parser.add_argument('--uri', nargs='?', help='Optional narrow down list from specific Rapp repository')

    parsed_args = parser.parse_args(args)

    if not parsed_args.uri:
        index = get_combined_index()
    else:
        uri = sanitize_uri(parsed_args.uri)
        index = get_index(uri)

    compatible_rapps, incompatible_rapps, invalid_rapps = index.get_compatible_rapps(ancestor_share_check=False)

    dependency_checker = DependencyChecker(index)
    rapp_deps = dependency_checker.check_rapp_dependencies(compatible_rapps)

    runnable_rapps = {}
    installable_rapps = {}
    noninstallable_rapps = {}
    for rapp in rapp_deps:
        if rapp_deps[rapp].all_installed():
            runnable_rapps[rapp] = compatible_rapps[rapp]
        elif rapp_deps[rapp].any_not_installable():
            noninstallable_rapps[rapp] = compatible_rapps[rapp]
        else:
            installable_rapps[rapp] = compatible_rapps[rapp]

    print('== Installed Rapp List == ')
    for n in runnable_rapps.values():
        print('  Resource: %s' % (str(n.resource_name)))
        print('     - Compatibility : %s ' % str(n.data['compatibility']))
        print('     - Ancestor      : %s ' % str(n.ancestor_name))

    if len(installable_rapps) > 0:
        print('== Installable Rapp List == ')
        for k, v in installable_rapps.items():
            print('  ' + k + ' : ' + str(v))

    if len(noninstallable_rapps) > 0:
        print('== Noninstallable Rapp List == ')
        for k, v in noninstallable_rapps.items():
            print('  ' + k + ' : ' + str(v))

    if len(invalid_rapps) > 0:
        print('== Invalid Rapp List == ')
        for k, v in invalid_rapps.items():
            print('  ' + k + ' : ' + str(v))


def _rapp_cmd_raw_info(argv):
    print("Displays rapp raw information")
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Displays rapp information')
    parser.add_argument('resource_name', type=str, help='Rapp name')

    parsed_args = parser.parse_args(args)
    resource_name = parsed_args.resource_name

    index = get_combined_index()

    rapp = index.get_raw_rapp(resource_name)

    print('== %s ==' % str(rapp))
    for k, v in rapp.raw_data.items():
        print('  %s : %s' % (str(k), str(v)))

def _rapp_cmd_info(argv):
    print("Displays rapp resolved information")
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Displays rapp information')
    parser.add_argument('resource_name', type=str, help='Rapp name')

    parsed_args = parser.parse_args(args)
    resource_name = parsed_args.resource_name

    index = get_combined_index()
    try:
        rapp = index.get_rapp(resource_name)
        print('== %s ==' % str(rapp))
        for k, v in rapp.raw_data.items():
            print('  %s : %s' % (str(k), str(v)))
    except Exception as e:
        print('%s : Error - %s' % (resource_name, str(e)))


#def _rapp_cmd_depends(argv):
#    print("Dependecies")
#    pass


def _rapp_cmd_depends_on(argv):
    print("Childs")
    pass


#def _rapp_cmd_profile(argv):
#    indexer = RappIndexer()
#    pass


def _rapp_cmd_compat(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Displays list of compatible rapps')
    parser.add_argument('compatibility', type=str, help='Rocon URI')

    parsed_args = parser.parse_args(args)
    compatibility = parsed_args.compatibility

    index = get_combined_index()
    compatible_rapps, incompatible_rapps, invalid_rapps = index.get_compatible_rapps(compatibility)

    print('== Available Rapp List for [%s] == ' % compatibility)
    for r in compatible_rapps.values():
        print('  Resource: %s' % (str(r.resource_name)))
        print('     - Ancestor : %s ' % str(r.ancestor_name))

    print('== Incompatible Rapp List for [%s] == ' % compatibility)
    for k, v in incompatible_rapps.items():
        print('  ' + k + ' : ' + str(v.raw_data['compatibility']))

    print('== Invalid Rapp List for [%s] == ' % compatibility)
    for k, v in invalid_rapps.items():
        print('  ' + k + ' : ' + str(v))


def _rapp_cmd_install(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Install a list of rapps')
    parser.add_argument('--debug', action='store_true', help='Output debug information')
    parser.add_argument('rapp_names', type=str, nargs='+', help='Rocon URI')

    parsed_args = parser.parse_args(args)
    rapp_names = set(parsed_args.rapp_names)

    index = get_combined_index()

    dependencyChecker = DependencyChecker(index)

    dependencies = dependencyChecker.check_rapp_dependencies(rapp_names)
    missing_dependencies = []
    rapp_deps_list = {}
    for rapp_name, deps in dependencies.items():
        missing_dependencies.extend(deps.noninstallable)
        rapp_deps_list[rapp_name] = deps.installable
    missing_dependencies = set(missing_dependencies)

    noninstallable_rapps = [rapp_name for rapp_name, deps in dependencies.items() if deps.noninstallable]
    if noninstallable_rapps:
        print('Error - The following rapps cannot be installed: %s. Missing dependencies: %s' % (' '.join(noninstallable_rapps.keys()),
                                                                                                 ' '.join(missing_dependencies)
                                                                                                ))
    else:
        # cache rapps' dependencies
        _cache_rapp_deps(rapp_deps_list)
        # resolve deps and install them
        print("Installing dependencies for: %s" % (' '.join(sorted(rapp_names))))
        if parsed_args.debug:
            print("- installing the following packages: %s" % ' '.join(sorted(set([d for deps in dependencies.values() for d in deps.installable]))))
            print("- already installed packages: %s" % ' '.join(sorted(set([d for deps in dependencies.values() for d in deps.installed]))))
        dependencyChecker.install_rapp_dependencies(rapp_names)


def _rapp_cmd_uninstall(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Uninstall a list of rapps')
    parser.add_argument('--debug', action='store_true', help='Output debug information')
    parser.add_argument('rapp_names', type=str, nargs='+', help='Rocon URI')
    parsed_args = parser.parse_args(args)
    rapp_names = set(parsed_args.rapp_names)

    if not os.path.isfile(RAPP_DEPS_CACHE_FILE):
        print("Could not find the cache file [%s]" % RAPP_DEPS_CACHE_FILE)
        return

    with open(os.path.abspath(RAPP_DEPS_CACHE_FILE), 'r') as f:
        rapp_deps_cache = yaml.load(f)

    for rapp_name in rapp_names:
        print("\nRemoving dependencies for rapp '%s':" % rapp_name)
        none_removed = True
        for cache_dep, cache_rapps in rapp_deps_cache.items():
            if rapp_name in cache_rapps:
                if len(cache_rapps) == 1:
                    print("Removing dependency '%s'." % (cache_dep))
                    sub_command = ["sudo", "apt-get", "remove", "-y", cache_dep]
                    print("\033[1mexecuting command [%s]\033[0m" % ' '.join(sub_command))
                    result = subprocess.call(sub_command)
                    if result != 0:
                        print('command [%s] failed' % (' '.join(sub_command)))
                        return
                    del rapp_deps_cache[cache_dep]
                    none_remove = False
                else:
                    print("Cannot remove dependency '%s', since other rapps depend on it." % (cache_dep))
        if none_removed:
            print("No dependencies are installed for rapp '%s' or they are all locked by other rapps.\n" % rapp_name)

    with open(os.path.abspath(RAPP_DEPS_CACHE_FILE), 'w') as f:
        yaml.dump(rapp_deps_cache, f)


def _rapp_cmd_index(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Generate an index for a Rapp tree')
    parser.add_argument('packages_path', type=str, help='Path to a Rapp tree')

    parsed_args = parser.parse_args(args)
    packages_path = parsed_args.packages_path

    index_path(packages_path)


def index_path(packages_path):
    index = build_index([packages_path])
    base_path = os.path.dirname(packages_path)
    filename_prefix = os.path.basename(packages_path)
    dest_prefix = os.path.join(base_path, filename_prefix)
    index.write_tarball(dest_prefix)


def _rapp_cmd_add_repository(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Add a rapp repository')
    parser.add_argument('repository_url', type=str, help='URL of a Rapp repository index or a local folder')

    parsed_args = parser.parse_args(args)
    repository_url = parsed_args.repository_url

    uris = load_uris()
    if repository_url in uris:
        raise RuntimeError("'%s' is already listed as a rapp repository" % repository_url)
    repository_url = sanitize_uri(repository_url)
    if os.path.isdir(repository_url) or os.path.isfile(repository_url):
        repository_url = os.path.abspath(repository_url)
    uris.append(repository_url)
    save_uris(uris)


def _rapp_cmd_remove_repository(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Remove a rapp repository')
    parser.add_argument('repository_url', type=str, help='URL of a Rapp repository index or a local folder')

    parsed_args = parser.parse_args(args)
    repository_url = parsed_args.repository_url

    uris = load_uris()
    if repository_url not in uris:
        raise RuntimeError("'%s' is not listed as a rapp repository" % repository_url)
    uris.remove(repository_url)
    save_uris(uris)


def _rapp_cmd_list_repositories(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='List rapp repositories')

    parser.parse_args(args)

    uris = load_uris()
    for uri in uris:
        print(uri)


def _rapp_cmd_update_repository_indices(argv):
    #  Parse command arguments
    args = argv[2:]
    parser = argparse.ArgumentParser(description='Update indices of rapp repositories')

    parser.parse_args(args)

    update_indices()


def update_indices():
    uris = load_uris()
    for uri in uris:
        # existing indices must not be updated
        if is_index(uri):
            continue
        url = uri2url(uri)
        index = build_index(url)
        dest_prefix = get_index_dest_prefix_for_base_paths(url)
        index.write_tarball(dest_prefix)


def _fullusage():
    print("""\nrocon_app is a command-line tool for printing information about Rapp

Commands:
\trocon_app list\t\tdisplay a list of cached rapps
\trocon_app info\t\tdisplay rapp information
\trocon_app rawinfo\tdisplay rapp raw information
\trocon_app compat\tdisplay a list of rapps that are compatible with the given rocon uri
\trocon_app install\tinstall a list of rapps
\trocon_app uninstall\tuninstall a list of rapps
\trocon_app add-repo\tadd a rapp repository
\trocon_app remove-repo\tremove a rapp repository
\trocon_app list-repos\tlist the rapp repositories
\trocon_app update\tupdate the indices for the rapp repositories
\trocon_app index\t\tgenerate an index file of a Rapp tree
\trocon_app help\t\tUsage

Type rocon_app <command> -h for more detailed usage, e.g. 'rocon_app info -h'
""")
    sys.exit(getattr(os, 'EX_USAGE', 1))


# Future TODO    
#\trocon_app depends\tdisplay a rapp dependency list
#\trocon_app depends-on\tdisplay a list of rapps that depend on the given rapp
#\trocon_app profile\tupdate cache


#################################################################################
# Main
#################################################################################

def main():
    argv = sys.argv

    # process argv
    if len(argv) == 1:
        _fullusage()
    try:
        command = argv[1]
        if command == 'list':
            _rapp_cmd_list(argv)
        elif command == 'info':
            _rapp_cmd_info(argv)
        elif command == 'rawinfo':
            _rapp_cmd_raw_info(argv)
        elif command == 'depends':
            _rapp_cmd_depends(argv)
        elif command == 'depends-on':
            _rapp_cmd_depends_on(argv)
        elif command == 'profile':
            _rapp_cmd_profile(argv)
        elif command == 'compat':
            _rapp_cmd_compat(argv)
        elif command == 'install':
            _rapp_cmd_install(argv)
        elif command == 'uninstall':
            _rapp_cmd_uninstall(argv)
        elif command == 'index':
            _rapp_cmd_index(argv)
        elif command == 'add-repo':
            _rapp_cmd_add_repository(argv)
        elif command == 'remove-repo':
            _rapp_cmd_remove_repository(argv)
        elif command == 'list-repos':
            _rapp_cmd_list_repositories(argv)
        elif command == 'update':
            _rapp_cmd_update_repository_indices(argv)
        elif command == 'help':
            _fullusage()
        else:
            _fullusage()
    except RuntimeError as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    except Exception as e:
        sys.stderr.write("Error: %s\n" % str(e))
        ex, val, tb = sys.exc_info()
        traceback.print_exception(ex, val, tb)

        sys.exit(1)
