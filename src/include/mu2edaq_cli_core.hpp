// mu2edaq_cli_core.hpp -- shared helpers for the C++ side of the Mu2e DAQ
// command line tools.
//
// The config file lookup here mirrors mu2edaq_commandline_tools.config in the
// Python package, so a C++ tool and a Python tool started from the same place
// read the same YAML file.

#ifndef MU2EDAQ_CLI_CORE_HPP
#define MU2EDAQ_CLI_CORE_HPP

#include <string>
#include <vector>

namespace mu2edaq {
namespace cli {

/// Package version, kept in step with mu2edaq_commandline_tools.__version__.
const char* version();

/// Environment variable prefix shared with the Python tools.
const char* env_prefix();

/// Candidate config file locations, most specific first. When @p explicit_path
/// is non-empty it is the only candidate.
std::vector<std::string> config_search_paths(const std::string& explicit_path = "");

/// First candidate from config_search_paths() that exists, or "" if none do.
std::string find_config(const std::string& explicit_path = "");

/// Value of MU2EDAQ_TOOLS_<key> (key upper-cased), or @p fallback if unset or
/// empty.
std::string env_override(const std::string& key, const std::string& fallback = "");

}  // namespace cli
}  // namespace mu2edaq

#endif  // MU2EDAQ_CLI_CORE_HPP
