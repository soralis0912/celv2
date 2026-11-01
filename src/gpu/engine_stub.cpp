// GpuEngine for a build without CUDA (CELV2_CUDA off): the probe always fails, so make_engine
// (pipeline.cpp) falls back to Vulkan or the CPU, and --device gpu reports why.
#include "gpu/engine.h"

#include <stdexcept>

struct GpuEngine::Impl {};

namespace {

[[noreturn]] void no_cuda() { throw std::runtime_error("this celv2enc was built without CUDA"); }

}  // namespace

GpuEngine::GpuEngine(int, int, int) { no_cuda(); }

GpuEngine::~GpuEngine() = default;

ProbeResult probe_gpu() {
  ProbeResult r;
  r.reason = "this celv2enc was built without CUDA";
  return r;
}

DecisionMap GpuEngine::decide_intra(const Frame420&, int) { no_cuda(); }
DecisionMap GpuEngine::decide_inter(const Frame420&, const Frame420&, int) { no_cuda(); }
DecisionMap GpuEngine::decide_inter(const Frame420&, const std::vector<const Frame420*>&, int) { no_cuda(); }
void GpuEngine::prepare(const Frame420&, long long) { no_cuda(); }
void GpuEngine::launch(const Frame420&, const std::vector<const Frame420*>&, int, DecisionMap&,
                       const std::vector<long long>&, long long) {
  no_cuda();
}
void GpuEngine::set_row_streams(int) { no_cuda(); }
void GpuEngine::collect(DecisionMap&, RowGate&) { no_cuda(); }
std::vector<int64_t> GpuEngine::intra_costs(int) const { no_cuda(); }

std::vector<int> gpu_satd_batch(const uint8_t*, const uint8_t*, int, int, int) { no_cuda(); }
