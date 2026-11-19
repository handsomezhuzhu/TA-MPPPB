#ifndef REPLACEMENT_MPPPB_H
#define REPLACEMENT_MPPPB_H

#include <array>
#include <cstdint>
#include <deque>
#include <vector>

#include "cache.h"
#include "modules.h"

// MPPPB -- Multiperspective Placement, Promotion and Bypass.
//
// Independent implementation of the technique described in
//   D. A. Jimenez and E. Teran, "Multiperspective Reuse Prediction",
//   MICRO-50, 2017, pp. 436-448.
// No code from the authors or from any other MPPPB implementation is used.
// The feature table (parameters A/B/E/W/X) is the published Table 1(b), which
// is a fact of the paper, not code.
//
// Structure
//   * sixteen parameterized features index sixteen small tables of 6-bit
//     signed weights; the sum is a confidence that a block is dead;
//   * a 64-set x 18-way true-LRU sampler is trained on 1/32 of the cache sets;
//   * training is error-driven and per-feature (each feature has its own
//     associativity cutoff A);
//   * the confidence drives bypass, placement and promotion.
//
// Deviations from the paper (documented in docs/review_mpppb_code.md):
//   * the default policy is SRRIP (4 positions) instead of static MDPP (16);
//   * bypass is approximated by inserting at the LRU-most position and
//     marking the line as first-victim, because this ChampSim revision has no
//     "skip allocation" hook;
//   * the PC history is updated on LLC accesses, not on every memory access.
struct mpppb : public champsim::modules::replacement {
  explicit mpppb(CACHE* cache);
  ~mpppb();

  long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set,
                   champsim::address ip, champsim::address full_addr, access_type type);
  void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr,
                              champsim::address ip, champsim::address victim_addr, access_type type);
  void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr,
                                champsim::address ip, champsim::address victim_addr, access_type type, uint8_t hit);

private:
  enum class view : std::uint8_t { pc, address, bias, burst, insert, lastmiss, offset };

  struct feature {
    view kind;
    int a;              // recency position beyond which the block is dead
    int b;              // first bit of the slice (inclusive)
    int e;              // last bit of the slice (inclusive)
    int w;              // PC-history depth, 0 = current instruction
    bool mix_pc;        // XOR the slice with the current PC (bit 0 of X)
    std::uint8_t x_mask; // full X mask: bit 0 = XOR PC, bit 1 = prefetch toggle
    std::uint8_t bits;  // index width
    std::uint16_t entries;
  };

  struct item {
    bool used = false;
    std::uint16_t ptag = 0;                  // partial tag
    std::int16_t score = 0;                  // confidence seen on last touch
    std::array<std::uint8_t, 16> key{};      // table indices of that touch
  };

  struct sample_set {
    std::array<item, 18> line{};
  };

  struct core_view {
    std::vector<std::vector<std::int8_t>> table;
    std::vector<sample_set> sampler;
    std::array<std::uint64_t, 32> pc_ring{};
    std::uint64_t stamps = 0;
  };

  struct pending_hit {
    std::uint64_t block = 0;
    std::int16_t score = 0;
  };

  static constexpr int kFeatureCount = 16;
  static constexpr int kMaxRrpv = 3;
  static constexpr int kMaxWeight = 31;
  static constexpr int kMinWeight = -32;
  static constexpr int kSampleStride = 32;   // one sampled set per 32 sets
  static constexpr std::size_t kPendingCap = 64;

  long sets_;
  long ways_;
  std::size_t sampled_sets_;
  int set_bits_ = 6;

  std::vector<feature> plan_;
  std::vector<core_view> cores_;

  std::vector<std::int8_t> rrpv_;
  std::vector<std::uint8_t> first_victim_;  // bypass approximation
  std::vector<std::uint64_t> mru_block_;
  std::vector<std::uint8_t> miss_last_;
  std::vector<std::deque<pending_hit>> in_flight_;

  // The paper does not publish these; they are searched (environment overrides
  // keep the tuning script working).
  int thr_bypass_ = 150;
  int thr_pos1_ = 100;
  int thr_pos2_ = 50;
  int thr_pos3_ = 0;
  int thr_keep_ = 0;
  // Placement positions (pi1..pi3) in the four-level SRRIP default policy.
  int pos1_ = 3;
  int pos2_ = 3;
  int pos3_ = 2;

  // ---- author profile (CRC2 config 1/2: single-core MDPP) ----
  bool author_ = false;        // MDPP + author training + author feature set
  bool author2_ = false;       // CRC2 config 2: single-core MDPP with prefetcher
  bool improve_ = false;       // TA-MPPPB: translation/access-aware reuse prediction & protection
  // Granular Point 1 causal ablation & Point 2 TA-MPPPB controls (off by default):
  bool ab_write_nopc_ = false;
  bool ab_write_nosamp_ = false;
  bool ab_write_preserve_ = false;
  bool ab_trans_nobp_ = false;
  bool ab_trans_nopc_ = false;
  bool ab_trans_nosamp_ = false;
  int ab_trans_pos_ = -1;      // >=0 overrides TRANSLATION fill PLRU index (e.g. 0, 6, 8)
  bool ab_trans_promote_ = false;
  bool ab_pref_nobp_ = false;
  bool ab_pref_nopc_ = false;
  bool ab_pref_nosamp_ = false;
  bool ab_pref_nohash_ = false; // disable 0x9e3779b9^(block>>6) synthetic PC on PREFETCH
  int ab_pref_pos_ = -1;       // >=0 overrides PREFETCH fill PLRU index (instead of score)
  bool ab_mask_zero_pc_ = false; // ignore PC-only / XOR-PC features when ip==0
  bool ab_keep_pc_ring_ = false; // LOO: re-enable PC-ring updates from zero-PC / non-demand accesses
  int ab_write_pos_ = -1;      // >=0 overrides WRITE fill PLRU index
  int ab_write_hit_promote_ = 0; // 0=score-gated, 1=unconditional kVecMdpp, 2=unconditional MRU(0)
  int ab_pref_hit_promote_ = 0;  // 0=score-gated, 1=unconditional kVecMdpp, 2=unconditional MRU(0)
  int ab_demand_hit_promote_ = 0;// 0=score-gated, 1=unconditional kVecMdpp, 2=unconditional MRU(0)
  bool ab_write_duel_ = false;   // set-duel WRITE insertion between ab_write_pos_ and ab_write_pos2_
  int ab_write_pos2_ = 15;       // secondary WRITE fill PLRU index in set-dueling
  int wsel_ = 0;                 // 10-bit saturating duel counter for WRITE placement
  bool ab_pref_duel_ = false;    // set-duel PREFETCH insertion between ab_pref_pos_ and ab_pref_pos2_
  int ab_pref_pos2_ = 15;        // secondary PREFETCH fill PLRU index in set-dueling
  int pfsel_ = 0;                // 10-bit saturating duel counter for PREFETCH placement
  bool ab_trans_duel_ = false;   // set-duel TRANSLATION insertion between ab_trans_pos_ and ab_trans_pos2_
  int ab_trans_pos2_ = 15;       // secondary TRANSLATION fill PLRU index in set-dueling
  int tsel_ = 0;                 // 10-bit saturating duel counter for TRANSLATION placement
  int ab_duel_dem_w_ = 1;        // weight per LOAD/RFO miss in type set-dueling
  int ab_duel_own_w_ = 0;        // weight per own-class miss in type set-dueling
  bool use_mdpp_ = false;      // tree-based pseudo-LRU base
  bool direct_index_ = false;  // direct bit extraction + modulo (author code)
  bool author_train_ = false;  // init weight 1, threshold 128, dead zone
  bool bypass_duel_ = false;   // set-dueling for the bypass threshold
  int train_threshold_ = 0;    // dan_threshold: 128 single, 0 multi
  int theta_ = 0;              // dead-zone upper bound (109 single)
  int theta2_ = 0;             // dead-zone lower bound (135 single)
  int promotion_threshold_ = 256;
  int bypass_dt1_ = 55;
  int bypass_dt2_ = 1024;
  int leaders1_ = 32;
  int leaders2_ = 64;
  int psel_ = 0;               // set-dueling counter
  int init_weight_ = 0;        // author code initializes to 1
  int plv_[3][2] = {{-15, 0}, {35, 12}, {44, 15}};
  int last_promoted_ = 0;
  std::uint8_t burst_now_ = 0;
  std::vector<std::uint16_t> plru_;  // 15 bits per set (MDPP)

  static constexpr int kMdppWays = 16;

  int plru_index(long set, long way) const;
  void plru_set(long set, long way, int idx);
  bool plru_would_change(long set, long way, int idx) const;
  long plru_victim(long set) const;
  std::int16_t peek_score(long set, std::uint64_t block, bool& found) const;
  void drop_pending(long set, std::uint64_t block);
  int bypass_limit(long set) const;
  void promote_mdpp_way(long set, long way, int mode, std::int16_t score);
  int duel_fill_pos(long set, int pos1, bool duel, int pos2, long slot1, long slot2, int sel) const;
  std::uint64_t effective_ip(std::uint64_t ip, std::uint64_t block, access_type type) const;
  bool is_pref_isolated(long set) const;
  void update_type_duels(long set, access_type type);

  void describe_features();
  std::vector<std::int8_t>& weights(std::size_t cpu, int feature);
  std::uint8_t index_of(const feature& f, const core_view& st, long set, std::uint64_t ip,
                        std::uint64_t addr, std::uint64_t block, bool insert, access_type type);
  std::int16_t predict(core_view& st, long set, std::uint64_t ip, std::uint64_t addr, std::uint64_t block,
                       bool insert, access_type type, std::array<std::uint8_t, kFeatureCount>& key);
  void visit_sampler(core_view& st, long set, std::uint16_t ptag, std::int16_t score,
                     const std::array<std::uint8_t, kFeatureCount>& key, access_type type);
  void learn_reuse(core_view& st, const item& old, int position);
  void learn_demote(core_view& st, const item& old, int new_position);
  void nudge(core_view& st, int feature, std::uint8_t index, int delta);
  std::uint16_t partial_tag(std::uint64_t block) const;
  std::int16_t take_score(long set, std::uint64_t block, bool& found);
};

#endif