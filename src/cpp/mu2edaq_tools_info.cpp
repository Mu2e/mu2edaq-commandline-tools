// mu2edaq-tools-info -- report what the C++ tools would use for configuration.
//
// Diagnostic counterpart to `mu2edaq-tools config`: it answers "which YAML file
// would a C++ tool started here actually read?" without running anything else.

#include "mu2edaq_cli_core.hpp"

#include <cstring>
#include <iostream>
#include <string>

namespace {

void usage(const char* prog) {
  std::cout
      << "Usage: " << prog << " [options]\n\n"
      << "Report the version and the config file the Mu2e DAQ command line\n"
      << "tools would use from the current working directory.\n\n"
      << "Options:\n"
      << "  -c, --config FILE   use FILE instead of searching\n"
      << "  -p, --paths         list every candidate path, marking the hits\n"
      << "  -V, --version       print the version and exit\n"
      << "  -h, --help          show this help and exit\n\n"
      << "Environment:\n"
      << "  MU2EDAQ_TOOLS_CONFIG   config file to use when --config is absent\n";
}

}  // namespace

int main(int argc, char** argv) {
  std::string explicit_path;
  bool show_paths = false;

  for (int i = 1; i < argc; ++i) {
    const char* a = argv[i];
    if (!std::strcmp(a, "-h") || !std::strcmp(a, "--help")) {
      usage(argv[0]);
      return 0;
    } else if (!std::strcmp(a, "-V") || !std::strcmp(a, "--version")) {
      std::cout << "mu2edaq-tools-info " << mu2edaq::cli::version() << "\n";
      return 0;
    } else if (!std::strcmp(a, "-p") || !std::strcmp(a, "--paths")) {
      show_paths = true;
    } else if (!std::strcmp(a, "-c") || !std::strcmp(a, "--config")) {
      if (i + 1 >= argc) {
        std::cerr << argv[0] << ": " << a << " requires a file argument\n";
        return 2;
      }
      explicit_path = argv[++i];
    } else {
      std::cerr << argv[0] << ": unknown option " << a << "\n";
      usage(argv[0]);
      return 2;
    }
  }

  std::cout << "version:     " << mu2edaq::cli::version() << "\n";
  const std::string found = mu2edaq::cli::find_config(explicit_path);
  std::cout << "config file: " << (found.empty() ? "(none found, using defaults)" : found)
            << "\n";

  if (show_paths) {
    std::cout << "candidates:\n";
    for (const std::string& p : mu2edaq::cli::config_search_paths(explicit_path)) {
      std::cout << "  " << (p == found ? "*" : " ") << " " << p << "\n";
    }
  }
  return 0;
}
