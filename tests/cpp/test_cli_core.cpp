// Unit tests for mu2edaq::cli. Built against CppUnit when it is available,
// otherwise the same checks run through a plain assert() driver so that the
// suite is never silently skipped.

#include "mu2edaq_cli_core.hpp"

#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

bool ends_with(const std::string& s, const std::string& suffix) {
  return s.size() >= suffix.size() &&
         s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

void check_version_is_populated(bool& ok) {
  const std::string v = mu2edaq::cli::version();
  ok = ok && !v.empty() && v.find('.') != std::string::npos;
}

void check_explicit_path_is_only_candidate(bool& ok) {
  const std::vector<std::string> paths =
      mu2edaq::cli::config_search_paths("/tmp/does-not-exist.yaml");
  ok = ok && paths.size() == 1 && paths[0] == "/tmp/does-not-exist.yaml";
}

void check_search_covers_cwd_and_etc(bool& ok) {
  const std::vector<std::string> paths = mu2edaq::cli::config_search_paths();
  ok = ok && paths.size() >= 2;
  const bool has_cwd_config =
      std::any_of(paths.begin(), paths.end(), [](const std::string& p) {
        return ends_with(p, "mu2edaq-commandline-tools.yaml");
      });
  const bool has_etc =
      std::any_of(paths.begin(), paths.end(), [](const std::string& p) {
        return p == "/etc/mu2edaq/commandline-tools.yaml";
      });
  ok = ok && has_cwd_config && has_etc;
}

void check_missing_config_returns_empty(bool& ok) {
  ok = ok && mu2edaq::cli::find_config("/tmp/definitely-not-here-42.yaml").empty();
}

void check_env_override(bool& ok) {
#ifndef _WIN32
  setenv("MU2EDAQ_TOOLS_CLUSTER", "testbed", 1);
  ok = ok && mu2edaq::cli::env_override("cluster", "mu2edaq") == "testbed";
  unsetenv("MU2EDAQ_TOOLS_CLUSTER");
#endif
  ok = ok && mu2edaq::cli::env_override("no_such_key", "fallback") == "fallback";
}

}  // namespace

#ifdef HAVE_CPPUNIT

#include <cppunit/TestFixture.h>
#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/ui/text/TestRunner.h>

class CliCoreTest : public CppUnit::TestFixture {
  CPPUNIT_TEST_SUITE(CliCoreTest);
  CPPUNIT_TEST(testVersion);
  CPPUNIT_TEST(testExplicitPath);
  CPPUNIT_TEST(testSearchPaths);
  CPPUNIT_TEST(testMissingConfig);
  CPPUNIT_TEST(testEnvOverride);
  CPPUNIT_TEST_SUITE_END();

 public:
  void testVersion() {
    bool ok = true;
    check_version_is_populated(ok);
    CPPUNIT_ASSERT(ok);
  }
  void testExplicitPath() {
    bool ok = true;
    check_explicit_path_is_only_candidate(ok);
    CPPUNIT_ASSERT(ok);
  }
  void testSearchPaths() {
    bool ok = true;
    check_search_covers_cwd_and_etc(ok);
    CPPUNIT_ASSERT(ok);
  }
  void testMissingConfig() {
    bool ok = true;
    check_missing_config_returns_empty(ok);
    CPPUNIT_ASSERT(ok);
  }
  void testEnvOverride() {
    bool ok = true;
    check_env_override(ok);
    CPPUNIT_ASSERT(ok);
  }
};

CPPUNIT_TEST_SUITE_REGISTRATION(CliCoreTest);

int main() {
  CppUnit::TextUi::TestRunner runner;
  runner.addTest(CppUnit::TestFactoryRegistry::getRegistry().makeTest());
  return runner.run() ? 0 : 1;
}

#else  // no CppUnit

#include <cassert>
#include <iostream>

int main() {
  bool ok = true;
  check_version_is_populated(ok);
  check_explicit_path_is_only_candidate(ok);
  check_search_covers_cwd_and_etc(ok);
  check_missing_config_returns_empty(ok);
  check_env_override(ok);
  if (!ok) {
    std::cerr << "test_cli_core: FAILED (CppUnit not available, "
                 "ran the assert-based driver)\n";
    return 1;
  }
  std::cout << "test_cli_core: OK (5 checks, CppUnit not available)\n";
  return 0;
}

#endif
