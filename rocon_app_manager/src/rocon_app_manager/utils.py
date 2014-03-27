#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_app_platform/license/LICENSE
#
##############################################################################

import rospy
import roslaunch.parent
import tempfile
import roslib.names
import rocon_std_msgs.msg as rocon_std_msgs

##############################################################################
# Utilities
##############################################################################


def dict_to_KeyValue(d):
    '''
      Converts a dictionary to key value ros msg type.

      :param d: dictionary
      :type d: dict

      :returns: KeyValue ros message
      :rtype: [rocon_std_msgs.KeyValue]
    '''
    l = []
    for k, v in d.iteritems():
        l.append(rocon_std_msgs.KeyValue(k, str(v)))
    return l


def _prepare_launch_text(launch_file, launch_args, application_namespace,
                         gateway_name, rocon_uri_string, capability_server_nodelet_manager_name=None):
    '''
      Prepare the launch file text. This essentially wraps the rapp launcher
      with the following roslaunch elements:

      - group namespace
      - roslaunch args

      The roslaunch args are a list of string keys used to select which
      automatically generated roslaunch args (e.g. namespace, name,
      rocon_uri properties) should get passed to the rapp. Note that we
      don't pass the whole set, because roslaunch args will throw an error
      if the rapp itself isn't expecting them. The logoc for determing this is
      in get_standard_args.

      :param launch_file: fully resolved launch file path
      :type launch_file: str
      :param launch_args: strings identifying the keys of the standard roslaunch args
             to send (not the args themselves)
      :type launch_args: [str]
      :param application_namespace: unique name granted indirectly via the
             gateways, we namespace everything under this
      :type application_namespace: str
      :param gateway_name: unique name granted to the gateway
      :type gateway_name: str
      :param rocon_uri_string: used to pass down information about the platform that is running this app to the app itself.
      :type rocon_uri_string: str - a rocon uri string

      The rocon_uri_string variable is a fixed identifier for this app manager's platform - i.e. no special
      characters or wildcards should be contained therein.
    '''

    # Prepare argument mapping
    launch_arg_mapping = {}
    launch_arg_mapping['application_namespace'] = application_namespace
    launch_arg_mapping['gateway_name'] = gateway_name
    launch_arg_mapping['rocon_uri'] = rocon_uri_string
    launch_arg_mapping['capability_server_nodelet_manager_name'] = capability_server_nodelet_manager_name

    launch_text = '<launch>\n  <include ns="%s" file="%s">\n' % (application_namespace, launch_file)
    for arg in launch_args:
        launch_text += '    <arg name="%s" value="%s"/>' % (arg, launch_arg_mapping[arg])
    launch_text += '  </include>\n</launch>\n'
    return launch_text


def resolve_chain_remappings(nodes):
    '''
        Resolve chain remapping rules contained in node remapping arguments
        replace the node remapping argument

        :param nodes: roslaunch nodes
        :type nodes: roslaunch.Nodes[]
    '''
    for n in nodes:
        new_remap_args_dict = {}

        for fr, to in n.remap_args:
            if str(fr) in new_remap_args_dict:
                rospy.logwarn("App Manager : Remapping rule for %s already exists. Ignoring remapping rule from %s to %s", str(fr), str(fr), str(to))
            else:
                # if there is a value which matches with remap_from, the value should be replaced with the new remap_to
                keys = [k for k, v in new_remap_args_dict.items() if v == str(fr)]
                for k in keys:
                    new_remap_args_dict[k] = str(to)

                new_remap_args_dict[str(fr)] = str(to)
        n.remap_args = new_remap_args_dict.items()


def prepare_launcher(data, application_namespace, gateway_name, rocon_uri_string, nodelet_manager_name, force_screen, temp):
    '''
      prepare roslaunch to start rapp.
    '''
    # Create modified roslaunch file include the application namespace (robot name + 'application')

    launch_text = _prepare_launch_text(data['launch'],
                                       data['launch_args'],
                                       application_namespace,
                                       gateway_name,
                                       rocon_uri_string,
                                       nodelet_manager_name)
    temp.write(launch_text)
    temp.close()  # unlink it later

    launch = roslaunch.parent.ROSLaunchParent(rospy.get_param("/run_id"),
                                              [temp.name],
                                              is_core=False,
                                              process_listeners=(),
                                              force_screen=force_screen)
    launch._load_config()

    return launch


def apply_remapping_rules_from_capabilities(launch_spec, data, caps_list):
    '''
      applies remapping rules from capabilities

      :params launch_spec: rapp launch specification
      :type launch_spec: roslaunch.parent.ROSLaunchParent
      :params data: rapp data
      :type data: dict
      :param caps_list: this holds the list of available capabilities, if app needs capabilities
      :type caps_list: CapsList
    '''
    caps_remap_from_list = []  # contains the app's topics/services/actions to be remapped
    caps_remap_to_list = []  # contains the new topic/service/action names
    for cap in data['required_capabilities']:  # get capability-specific remappings
        rospy.loginfo("App Manager : Configuring remappings for capabilty '" + cap['name'] + "'.")
        if caps_list:
            caps_list.get_cap_remappings(cap, caps_remap_from_list, caps_remap_to_list)
        else:  # should not happen, since app would have been pruned
            raise Exception("Capabilities required, but capability list not provided.")
    for cap_remap in caps_remap_from_list:  # apply cap remappings
        remap_applied = False
        for node in launch_spec.config.nodes:  # look for cap remap topic is remap topics
            for node_remap in node.remap_args:  # topic from - topic to pairs
                if cap_remap in node_remap[0]:
                    node_remap[1] = unicode(caps_remap_to_list[caps_remap_from_list.index(cap_remap)])
                    rospy.loginfo("App Manager : Will remap '" + node_remap[0]
                                  + "' to '" + node_remap[1] + "'.")
                    remap_applied = True
        if not remap_applied:  # can't determine to which the remapping should be applied to
            rospy.logwarn("App Manager : Could not determine remapping for capability topic '"
                          + cap_remap + "'.")
            rospy.logwarn("App Manager : App might not function correctly."
                          + " Add it to the remapped topics, if needed.")


def apply_remapping_rules_from_start_app_request(launch_spec, data, remappings, application_namespace):
    '''
      applies remapping rules which are requested by start_app service

      :params launch_spec: rapp launch specification
      :type launch_spec: roslaunch.parent.ROSLaunchParent
      :params data: rapp data
      :type data: dict
      :param remapping: rules for the app flips.
      :type remapping: list of rocon_std_msgs.msg.Remapping values.
      :param application_namespace: unique name granted indirectly via the gateways, we namespace everything under this
      :type application_namespace: str

      :returns: Remapped public_interface dictionary
      :rtype: { connection_type: Remapping topic list}
    '''
    connections = {}

    # Prefix with robot name by default (later pass in remap argument)
    remap_from_list = [remapping.remap_from for remapping in remappings]
    remap_to_list = [remapping.remap_to for remapping in remappings]

    for connection_type in ['publishers', 'subscribers', 'services', 'action_clients', 'action_servers']:
        connections[connection_type] = []
        for t in data['public_interface'][connection_type]:
            remapped_name = None
            # Now we push the rapp launcher down into the prefixed
            # namespace, so just use it directly
            indices = [i for i, x in enumerate(remap_from_list) if x == t]
            if indices:
                if roslib.names.is_global(remap_to_list[indices[0]]):
                    remapped_name = remap_to_list[indices[0]]
                else:
                    remapped_name = '/' + application_namespace + "/" + remap_to_list[indices[0]]
                for N in launch_spec.config.nodes:
                    N.remap_args.append((t, remapped_name))
                connections[connection_type].append(remapped_name)
            else:
                # don't pass these in as remapping rules - they should map fine for the node as is
                # just by getting pushed down the namespace.
                #     https://github.com/robotics-in-concert/rocon_app_platform/issues/61
                # we still need to pass them back to register for flipping though.
                if roslib.names.is_global(t):
                    flipped_name = t
                else:
                    flipped_name = '/' + application_namespace + '/' + t
                connections[connection_type].append(flipped_name)
    return connections