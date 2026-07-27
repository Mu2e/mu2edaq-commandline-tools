#include "mu2edaq_cli_core.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>

namespace fs = std::filesystem;

namespace mu2edaq {
namespace cli {

namespace {

std::string getenv_str(const char* name) {
  const char* v = std::getenv(name);
  return v ? std::string(v) : std::string();
}

std::string home_dir() {
#ifdef _WIN32
  std::string home = getenv_str("USERPROFILE");
  if (home.empty()) home = getenv_str("HOMEDRIVE") + getenv_str("HOMEPATH");
  return home;
#else
  return getenv_str("HOME");
#endif
}

}  // namespace

const char* version() { return MU2EDAQ_CLI_VERSION; }

const char* env_prefix() { return "MU2EDAQ_TOOLS_"; }

std::vector<std::string> config_search_paths(const std::string& explicit_path) {
  std::vector<std::string> paths;
  if (!explicit_path.empty()) {
    paths.push_back(explicit_path);
    return paths;
  }

  const std::string from_env = getenv_str("MU2EDAQ_TOOLS_CONFIG");
  if (!from_env.empty()) paths.push_back(from_env);

  std::error_code ec;
  const fs::path cwd = fs::current_path(ec);
  if (!ec) {
    paths.push_back((cwd / "mu2edaq-commandline-tools.yaml").string());
    paths.push_back((cwd / "config" / "mu2edaq-commandline-tools.yaml").string());
  }

  const std::string home = home_dir();
  if (!home.empty()) {
    paths.push_back(
        (fs::path(home) / ".config" / "mu2edaq" / "commandline-tools.yaml").string());
  }
  paths.push_back("/etc/mu2edaq/commandline-tools.yaml");
  return paths;
}

std::string find_config(const std::string& explicit_path) {
  std::error_code ec;
  for (const std::string& p : config_search_paths(explicit_path)) {
    if (fs::is_regular_file(p, ec)) return p;
  }
  return std::string();
}

std::string env_override(const std::string& key, const std::string& fallback) {
  std::string name = env_prefix();
  for (char c : key) {
    name.push_back(static_cast<char>(
        std::toupper(static_cast<unsigned char>(c == '-' ? '_' : c))));
  }
  const std::string value = getenv_str(name.c_str());
  return value.empty() ? fallback : value;
}

}  // namespace cli
}  // namespace mu2edaq
