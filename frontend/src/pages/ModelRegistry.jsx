import React, { useState, useEffect } from 'react';
import { registryApi, systemApi } from '../services/api';
import SectionDivider from '../components/SectionDivider';
import SegmentedTabs from '../components/SegmentedTabs';

const ms = (value) => (Number.isFinite(value) ? `${value} ms` : 'Not measured');
const recorded = (value) => (Number.isFinite(value) ? value.toFixed(4) : 'Not recorded');
const valueSize = (value) => (Number.isFinite(value) ? 'text-2xl' : 'text-sm');
const metricNote = (value) =>
  Number.isFinite(value)
    ? 'Mean of 25 host-grouped CV folds; labels not human-verified'
    : 'Not in the registry entry of this build';

const ModelRegistry = () => {
  const [registryData, setRegistryData] = useState(null);
  const [activeVersionData, setActiveVersionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [validationResult, setValidationResult] = useState(null);
  const [validating, setValidating] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [versionA, setVersionA] = useState('');
  const [versionB, setVersionB] = useState('');
  const [latencyBench, setLatencyBench] = useState(null);
  const [benchmarking, setBenchmarking] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchRegistryData();
  }, []);

  const fetchRegistryData = async () => {
    setLoading(true);
    try {
      const [versionsRes, activeRes] = await Promise.all([
        registryApi.getVersions().catch(() => null),
        registryApi.getActive().catch(() => null),
      ]);
      if (versionsRes) {
        setRegistryData(versionsRes);
        if (versionsRes.versions && versionsRes.versions.length >= 2) {
          setVersionA(versionsRes.versions[0].version);
          setVersionB(versionsRes.versions[1].version);
        } else if (versionsRes.versions && versionsRes.versions.length === 1) {
          setVersionA(versionsRes.versions[0].version);
          setVersionB(versionsRes.versions[0].version);
        }
      }
      if (activeRes) {
        setActiveVersionData(activeRes);
      }
    } catch (err) {
      console.error('Error fetching model registry:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleValidateIntegrity = async (version) => {
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await registryApi.validate(version);
      setValidationResult(res);
      setActiveTab('verification');
    } catch (err) {
      setValidationResult({ valid: false, error: err.message || 'Validation request failed' });
    } finally {
      setValidating(false);
    }
  };

  const handleCompare = async () => {
    if (!versionA || !versionB) return;
    setComparing(true);
    try {
      const res = await registryApi.compare(versionA, versionB);
      setComparison(res);
    } catch (err) {
      setActionMessage({ type: 'error', text: `Comparison failed: ${err.message}` });
    } finally {
      setComparing(false);
    }
  };

  const handleRunLatencyBenchmark = async () => {
    setBenchmarking(true);
    try {
      const res = await systemApi.getLatencyBenchmark(25);
      setLatencyBench(res);
      setActiveTab('verification');
    } catch (err) {
      console.error('Benchmark failed:', err);
    } finally {
      setBenchmarking(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 rounded-full border-4 border-exosignal-cyan/20 border-t-exosignal-cyan animate-spin"></div>
        <p className="font-mono text-sm text-exosignal-text-muted">
          Loading Model Registry & Lineage Data...
        </p>
      </div>
    );
  }

  const registryTabs = [
    {
      id: 'overview',
      label: 'Active Deployment',
      icon: '🚀',
      badge: activeVersionData?.version || 'Active',
    },
    {
      id: 'catalog',
      label: 'Lineage Catalog',
      icon: '📦',
      badge: registryData?.total_versions || '0',
    },
    {
      id: 'verification',
      label: 'Integrity & Benchmarks',
      icon: '⚡',
      badge: validationResult ? (validationResult.valid ? 'Match' : 'Alert') : undefined,
    },
    {
      id: 'ab-compare',
      label: 'A/B Comparator',
      icon: '⚖️',
      badge: comparison ? 'Evaluated' : undefined,
    },
    { id: 'all', label: 'Full Governance View', icon: '📑' },
  ];

  const showAll = activeTab === 'all';

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-exosignal-cyan/20 pb-6">
        <div>
          <div className="flex items-center space-x-3 mb-2">
            <span className="text-2xl">🛡️</span>
            <h1 className="text-3xl font-black text-white font-display">
              Model Registry & Governance
            </h1>
          </div>
          <p className="text-sm text-exosignal-text-secondary max-w-3xl">
            Registered model builds with the SHA-256 checksums of their files. Metrics are those
            that a build recorded; they rest on labels that are not human-verified.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => handleValidateIntegrity(registryData?.active_version || 'active')}
            disabled={validating}
            className="btn-primary-glow text-xs"
          >
            {validating ? 'Verifying Hashes...' : '🔒 Verify SHA256 Hashes'}
          </button>
          <button
            onClick={handleRunLatencyBenchmark}
            disabled={benchmarking}
            className="btn-secondary-glass text-xs"
          >
            {benchmarking ? 'Benchmarking...' : '⚡ Bench Latency'}
          </button>
        </div>
      </div>

      {/* Modular Tab Division Control */}
      <div className="pt-1">
        <SegmentedTabs tabs={registryTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* SECTION 1: Active Model Deployment */}
      {(showAll || activeTab === 'overview') && (
        <div className="space-y-4">
          <SectionDivider
            number="01"
            title="Active Model Deployment Lineage"
            subtitle="The version the API serves. Verify Hashes compares its files with this entry"
            badge="ACTIVE MODEL"
            accent="cyan"
          />

          {activeVersionData && (
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-3">
                  <span className="pulsing-dot emerald"></span>
                  <div>
                    <span className="text-xs font-mono uppercase tracking-wider text-emerald-400 font-bold block">
                      Active Model Deployment
                    </span>
                    <h3 className="text-2xl font-bold font-mono text-white">
                      {activeVersionData.version}
                    </h3>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-x-2 text-xs font-mono text-exosignal-text-muted bg-space-inset px-3 py-1.5 rounded-xl border border-exosignal-cyan/20">
                  <span>Registered:</span>
                  <span className="text-white font-semibold">
                    {activeVersionData.registered_at?.slice(0, 19).replace('T', ' ')} UTC
                  </span>
                </div>
              </div>

              <div className="p-6 space-y-6">
                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-space-inset rounded-xl p-4 border border-exosignal-cyan/20 shadow-sm">
                    <span className="text-xs font-mono text-exosignal-text-muted">NDCG@10</span>
                    <div
                      className={`${valueSize(
                        activeVersionData.evaluation?.['ndcg@10']
                      )} font-bold font-mono text-exosignal-cyan mt-1`}
                    >
                      {recorded(activeVersionData.evaluation?.['ndcg@10'])}
                    </div>
                    <span className="text-[11px] text-exosignal-text-muted">
                      {metricNote(activeVersionData.evaluation?.['ndcg@10'])}
                    </span>
                  </div>

                  <div className="bg-space-inset rounded-xl p-4 border border-exosignal-cyan/20 shadow-sm">
                    <span className="text-xs font-mono text-exosignal-text-muted">
                      Mean Avg Precision (MAP)
                    </span>
                    <div
                      className={`${valueSize(
                        activeVersionData.evaluation?.map
                      )} font-bold font-mono text-exosignal-purple-light mt-1`}
                    >
                      {recorded(activeVersionData.evaluation?.map)}
                    </div>
                    <span className="text-[11px] text-exosignal-text-muted">
                      {metricNote(activeVersionData.evaluation?.map)}
                    </span>
                  </div>

                  <div className="bg-space-inset rounded-xl p-4 border border-exosignal-cyan/20 shadow-sm">
                    <span className="text-xs font-mono text-exosignal-text-muted">
                      Precision@10
                    </span>
                    <div
                      className={`${valueSize(
                        activeVersionData.evaluation?.['precision@10']
                      )} font-bold font-mono text-emerald-400 mt-1`}
                    >
                      {recorded(activeVersionData.evaluation?.['precision@10'])}
                    </div>
                    <span className="text-[11px] text-exosignal-text-muted">
                      {metricNote(activeVersionData.evaluation?.['precision@10'])}
                    </span>
                  </div>

                  <div className="bg-space-inset rounded-xl p-4 border border-exosignal-cyan/20 shadow-sm">
                    <span className="text-xs font-mono text-exosignal-text-muted">
                      Catalog Format
                    </span>
                    <div className="text-lg xl:text-2xl font-bold font-mono text-amber-400 mt-1">
                      Parquet + DuckDB
                    </div>
                    <span className="text-[11px] text-exosignal-text-muted">
                      In-Memory Columnar
                    </span>
                  </div>
                </div>

                {/* Training Lineage & Provenance */}
                <div className="pt-4 border-t border-exosignal-cyan/15 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono text-exosignal-text-secondary">
                  <div className="bg-space-inset p-3 rounded-xl border border-exosignal-cyan/10">
                    <span className="text-exosignal-text-muted block text-[10px]">Algorithm:</span>
                    <span className="text-white font-semibold text-xs">
                      {activeVersionData.training?.algorithm || 'Not recorded'}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3 rounded-xl border border-exosignal-cyan/10">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Inputs of the served model:
                    </span>
                    <span className="text-white font-semibold text-xs">
                      {activeVersionData.served_model_features ?? 'Not available'}
                    </span>
                    {activeVersionData.training?.n_features != null &&
                      activeVersionData.served_model_features != null &&
                      activeVersionData.training.n_features !==
                        activeVersionData.served_model_features && (
                        <span className="text-exosignal-text-muted block text-[10px]">
                          The registry entry says {activeVersionData.training.n_features}: it
                          counted only the list of most important inputs.
                        </span>
                      )}
                  </div>
                  <div className="bg-space-inset p-3 rounded-xl border border-exosignal-cyan/10">
                    <span className="text-exosignal-text-muted block text-[10px]">Evaluation:</span>
                    <span className="text-white font-semibold text-xs">
                      Cross-validation grouped by host star (25 folds). No separate test set; the
                      final model is fitted on all eligible planets.
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SECTION 2: Registered Versions Table */}
      {(showAll || activeTab === 'catalog') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Artifact Provenance Catalog"
            subtitle="Registered builds and the metrics they recorded (— = not recorded)"
            badge="CATALOG"
            accent="purple"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <div>
                <h3 className="text-base font-bold text-white font-display">
                  Registered Model Builds
                </h3>
                <p className="text-xs font-mono text-exosignal-text-muted">
                  Cross-validation metrics on labels that are not human-verified
                </p>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-space-inset border border-exosignal-purple/30 text-purple-300 font-bold">
                {registryData?.total_versions || 0} Registered Builds
              </span>
            </div>

            <div className="p-6">
              <div className="overflow-x-auto rounded-xl border border-exosignal-cyan/20">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-exosignal-cyan/20 bg-space-inset text-exosignal-text-muted text-left">
                      <th className="py-3 px-4">Version Tag</th>
                      <th className="py-3 px-4">Deployment Status</th>
                      <th className="py-3 px-4">NDCG@10</th>
                      <th className="py-3 px-4">MAP</th>
                      <th className="py-3 px-4">Precision@10</th>
                      <th className="py-3 px-4">Registration Date</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-exosignal-cyan/10 bg-space-inset">
                    {registryData?.versions?.map((v) => {
                      const isProduction =
                        v.version === registryData?.active_version || v.status === 'production';
                      return (
                        <tr key={v.version} className="hover:bg-space-card-hover transition-colors">
                          <td className="py-3 px-4 font-bold text-white">{v.version}</td>
                          <td className="py-3 px-4">
                            {isProduction ? (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-[10px] font-bold">
                                ACTIVE
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full bg-slate-700/40 text-slate-400 border border-slate-600/40 text-[10px]">
                                {(v.status || 'unknown').toUpperCase()}
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-exosignal-cyan font-bold">
                            {v.ndcg_at_10 != null ? v.ndcg_at_10.toFixed(4) : '—'}
                          </td>
                          <td className="py-3 px-4 text-exosignal-purple-light font-bold">
                            {v.map != null ? v.map.toFixed(4) : '—'}
                          </td>
                          <td className="py-3 px-4 text-emerald-400 font-bold">
                            {v.precision_at_10 != null ? v.precision_at_10.toFixed(4) : '—'}
                          </td>
                          <td className="py-3 px-4 text-exosignal-text-muted">
                            {v.registered_at?.slice(0, 10)}
                          </td>
                          <td className="py-3 px-4 text-right space-x-2">
                            <button
                              onClick={() => handleValidateIntegrity(v.version)}
                              className="px-2.5 py-1 rounded bg-exosignal-cyan/10 hover:bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/30 text-[11px] transition-colors"
                            >
                              Verify Hashes
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Integrity Verification & Benchmark Telemetry */}
      {(showAll || activeTab === 'verification') && (
        <div className="space-y-6">
          <SectionDivider
            number="03"
            title="Integrity Verification & Benchmarks"
            subtitle="Comparison of file checksums with the registry, and timing of database queries"
            badge="DIAGNOSTICS"
            accent="emerald"
          />

          <div className="grid grid-cols-1 gap-6">
            {/* Validation Result Box */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-2">
                  <span className="text-xl">🔒</span>
                  <h3 className="text-base font-bold text-white font-display">
                    SHA-256 Checksum Integrity Audit
                  </h3>
                </div>
                {validationResult && (
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-mono font-bold ${
                      validationResult.valid
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                    }`}
                  >
                    {validationResult.valid ? 'CHECKSUMS MATCH' : 'CHECKSUM MISMATCH OR MISSING'}
                  </span>
                )}
              </div>

              <div className="p-6">
                {validationResult ? (
                  <div className="space-y-4">
                    <p className="text-xs font-mono text-exosignal-text-secondary">
                      Active Model Version:{' '}
                      <span className="text-white font-bold">{validationResult.version}</span> •
                      file checksums compared with those in the registry entry
                    </p>

                    {validationResult.checks && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(validationResult.checks).map(([key, check]) => (
                          <div
                            key={key}
                            className="bg-space-inset rounded-xl p-4 border border-exosignal-cyan/20 text-xs font-mono space-y-1.5"
                          >
                            <div className="flex justify-between items-center">
                              <span className="text-exosignal-cyan uppercase font-bold">
                                {key} Artifact
                              </span>
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  check.status === 'OK'
                                    ? 'bg-emerald-500/20 text-emerald-400'
                                    : 'bg-rose-500/20 text-rose-400'
                                }`}
                              >
                                {check.status}
                              </span>
                            </div>
                            <div className="text-[11px] text-exosignal-text-muted truncate">
                              Hash: {check.expected_sha256}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-3">
                    <div className="text-3xl">🛡️</div>
                    <p className="text-sm text-exosignal-text-secondary">
                      No verification report generated in this session yet.
                    </p>
                    <button
                      onClick={() =>
                        handleValidateIntegrity(registryData?.active_version || 'active')
                      }
                      disabled={validating}
                      className="btn-primary-glow text-xs"
                    >
                      {validating ? 'Verifying Hashes...' : 'Run SHA256 Verification Now'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Latency Benchmark Result */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-2">
                  <span className="text-xl">⚡</span>
                  <h3 className="text-base font-bold text-white font-display">
                    DuckDB Query Timing
                  </h3>
                </div>
                {latencyBench && (
                  <span className="text-xs font-mono text-emerald-400 font-bold bg-space-inset px-3 py-1 rounded-full border border-emerald-500/30">
                    {latencyBench.engine}
                  </span>
                )}
              </div>

              <div className="p-6">
                {latencyBench ? (
                  <div className="space-y-4">
                    <p className="text-xs font-mono text-exosignal-text-secondary">
                      {latencyBench.iterations} database queries, one after another, inside the API
                      process. Not a measurement of HTTP requests or of concurrent users.
                    </p>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-center">
                      <div className="bg-space-inset p-4 rounded-xl border border-exosignal-cyan/20">
                        <span className="text-xs text-exosignal-text-muted">
                          P50 Median Latency
                        </span>
                        <div className="text-2xl font-bold text-emerald-400 mt-1">
                          {ms(latencyBench.p50_ms)}
                        </div>
                      </div>
                      <div className="bg-space-inset p-4 rounded-xl border border-exosignal-cyan/20">
                        <span className="text-xs text-exosignal-text-muted">P95 Latency</span>
                        <div className="text-2xl font-bold text-exosignal-cyan mt-1">
                          {ms(latencyBench.p95_ms)}
                        </div>
                      </div>
                      <div className="bg-space-inset p-4 rounded-xl border border-exosignal-cyan/20">
                        <span className="text-xs text-exosignal-text-muted">P99 Latency</span>
                        <div className="text-2xl font-bold text-exosignal-purple-light mt-1">
                          {ms(latencyBench.p99_ms)}
                        </div>
                      </div>
                      <div className="bg-space-inset p-4 rounded-xl border border-exosignal-cyan/20">
                        <span className="text-xs text-exosignal-text-muted">Mean Latency</span>
                        <div className="text-2xl font-bold text-white mt-1">
                          {ms(latencyBench.mean_ms)}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-3">
                    <div className="text-3xl">⏱️</div>
                    <p className="text-sm text-exosignal-text-secondary">
                      Columnar query benchmark ready to execute against in-memory database.
                    </p>
                    <button
                      onClick={handleRunLatencyBenchmark}
                      disabled={benchmarking}
                      className="btn-secondary-glass text-xs"
                    >
                      {benchmarking
                        ? 'Running Benchmarks...'
                        : 'Run 25x Iteration Latency Benchmark'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 4: Model Version Comparison HUD */}
      {(showAll || activeTab === 'ab-compare') && (
        <div className="space-y-4">
          <SectionDivider
            number="04"
            title="A/B Model Version Comparator"
            subtitle="Side by side: the metrics that two builds recorded. No build is promoted or blocked here"
            badge="COMPARISON"
            accent="amber"
          />

          <div className="divided-compartment">
            <div className="compartment-header flex-col md:flex-row gap-4 [&>*]:max-w-full">
              <div>
                <h3 className="text-base font-bold text-white font-display">
                  A/B Evaluation Console
                </h3>
                <p className="text-xs font-mono text-exosignal-text-muted">
                  Select candidate and baseline builds to inspect NDCG@10, MAP, and Precision@10
                  deltas
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={versionA}
                  onChange={(e) => setVersionA(e.target.value)}
                  className="bg-space-inset border border-exosignal-cyan/30 rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                >
                  {registryData?.versions?.map((v) => (
                    <option key={v.version} value={v.version}>
                      Candidate: {v.version}
                    </option>
                  ))}
                </select>
                <span className="text-exosignal-text-muted text-xs font-mono font-bold">vs</span>
                <select
                  value={versionB}
                  onChange={(e) => setVersionB(e.target.value)}
                  className="bg-space-inset border border-exosignal-purple/30 rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                >
                  {registryData?.versions?.map((v) => (
                    <option key={v.version} value={v.version}>
                      Baseline: {v.version}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleCompare}
                  disabled={comparing}
                  className="btn-primary-glow text-xs"
                >
                  {comparing ? 'Comparing...' : 'Compare Versions'}
                </button>
              </div>
            </div>

            <div className="p-6">
              {actionMessage && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/20 text-rose-300 text-xs font-mono border border-rose-500/30">
                  {actionMessage.text}
                </div>
              )}

              {comparison && Object.keys(comparison.metric_comparison || {}).length === 0 ? (
                <div className="text-center py-8 text-xs font-mono text-exosignal-text-muted">
                  No metric is recorded for both builds, so there is nothing to compare.
                </div>
              ) : comparison ? (
                <div className="bg-space-inset rounded-xl p-5 border border-exosignal-purple/20">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                    {Object.entries(comparison.metric_comparison || {}).map(([metric, data]) => (
                      <div
                        key={metric}
                        className="p-4 bg-space-card rounded-xl border border-exosignal-cyan/20"
                      >
                        <div className="text-exosignal-text-muted uppercase text-[11px] font-bold tracking-wider">
                          {metric}
                        </div>
                        <div className="flex items-center justify-between mt-3">
                          <span className="text-white font-bold">
                            {versionA}:{' '}
                            {data[versionA] !== undefined ? data[versionA]?.toFixed(4) : 'N/A'}
                          </span>
                          <span className="text-exosignal-text-muted">vs</span>
                          <span className="text-white font-bold">
                            {versionB}:{' '}
                            {data[versionB] !== undefined ? data[versionB]?.toFixed(4) : 'N/A'}
                          </span>
                        </div>
                        <div className="mt-3 pt-2 border-t border-exosignal-cyan/15 text-right">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              data.winner === versionA
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-amber-500/20 text-amber-300'
                            }`}
                          >
                            {data.delta === 0
                              ? 'No difference'
                              : `Higher: ${data.winner} (${
                                  data.delta > 0 ? '+' : ''
                                }${data.delta?.toFixed(4)})`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-xs font-mono text-exosignal-text-muted">
                  Click <span className="text-exosignal-cyan font-bold">Compare Versions</span>{' '}
                  above to execute delta analysis between the selected models.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelRegistry;
