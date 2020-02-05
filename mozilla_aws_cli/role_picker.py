import os
import stat
import json.decoder
import logging
import platform
import requests
import tempfile

from .cache import read_group_role_map, write_group_role_map


logger = logging.getLogger(__name__)

PROMPT_BASH_CODE = r'''function maws_profile {
    test -n "${MAWS_PROMPT}" && echo " (${MAWS_PROMPT})"
}

if [ -n "${PS1##*\$(maws_profile)*}" ]; then
    # maws_profile is missing from PS1
    if [ "${PS1%\$ }" != "${PS1}" ]; then
        PS1="${PS1%\$ }\$(maws_profile)\$ "
    elif [ "${PS1% }" != "${PS1}" ]; then
        PS1="${PS1% }\$(maws_profile) "
    else
        PS1="${PS1}\$(maws_profile) "
    fi
fi'''


def output_set_env_vars(var_map):
    if platform.system() == "Windows":
        result = "\n".join(
            ["set {}={}".format(x, var_map[x]) for x in var_map])
    else:
        name = tempfile.mkstemp(suffix='.sh', prefix='maws-')[1]
        with open(name, 'w') as f:
            vars_to_set = [
                "=".join((x, var_map[x]))
                for x in var_map if var_map[x] is not None]
            if vars_to_set:
                f.write("export {}\n".format(" ".join(vars_to_set)))
            vars_to_unset = [x for x in var_map if var_map[x] is None]
            if vars_to_unset:
                f.write("unset {}\n".format(" ".join(vars_to_unset)))
            f.write("{}\n".format(PROMPT_BASH_CODE))
            f.write("rm -f {}\n".format(name))
            result = "source {}".format(name)
        st = os.stat(name)
        os.chmod(name, st.st_mode | stat.S_IEXEC)

    return result


def get_roles_and_aliases(endpoint, token, key, cache=True):
    role_map = read_group_role_map(endpoint)

    if role_map is None or not cache:
        headers = {"Content-Type": "application/json"}
        body = {
            "token": token,
            "key": key,
            "cache": cache
        }

        logging.debug("Getting roles and aliases from {} by POSTing {}".format(
            endpoint,
            body
        ))

        try:
            role_map = requests.post(
                endpoint, headers=headers, json=body).json()
        except requests.exceptions.ConnectionError as e:
            role_map = {"error": str(e)}
        except json.decoder.JSONDecodeError:
            logging.error("Unable to parse role map.")
            return None

        if role_map is None:
            logging.error(
                "Unable to retrieve role map at: {}. Please check your "
                "URL.".format(endpoint))
            return None
        elif "error" in role_map:
            logging.error(
                "Unable to retrieve role map: {}".format(role_map["error"]))
            return None
        else:
            write_group_role_map(endpoint, role_map)

    return role_map
