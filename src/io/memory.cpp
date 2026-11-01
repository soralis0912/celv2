#include "io/memory.h"

#include <cstdlib>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <unistd.h>
#endif

uint64_t installed_memory_bytes() {
  if (const char* t = std::getenv("CELV2_TEST_TOTAL_RAM_MB"); t && *t) return std::strtoull(t, nullptr, 10) << 20;  // tests/test_cli.cpp
#ifdef _WIN32
  MEMORYSTATUSEX m{};
  m.dwLength = sizeof(m);
  return GlobalMemoryStatusEx(&m) ? m.ullTotalPhys : 0;
#else
  const long pages = sysconf(_SC_PHYS_PAGES), page = sysconf(_SC_PAGE_SIZE);
  return pages > 0 && page > 0 ? static_cast<uint64_t>(pages) * static_cast<uint64_t>(page) : 0;
#endif
}
