import React from 'react';

/**
 * SegmentedTabs - Modular high-tech tab rail to divide dense pages into dedicated views
 */
const SegmentedTabs = ({
  tabs = [],
  activeTab,
  onChange,
  variant = 'pills', // 'pills' | 'underline' | 'boxed'
  className = '',
}) => {
  return (
    <div className={`w-full overflow-x-auto pb-1 ${className}`}>
      <div className="flex items-center space-x-2 p-1.5 rounded-2xl bg-space-void/90 border border-exosignal-cyan/25 backdrop-blur-xl shadow-inner min-w-max">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-mono font-bold transition-all duration-200 cursor-pointer ${
                isActive
                  ? 'bg-gradient-to-r from-exosignal-accent/30 to-exosignal-cyan/20 text-white border border-exosignal-cyan/50 shadow-[0_0_15px_rgba(56,189,248,0.3)]'
                  : 'text-exosignal-text-secondary hover:text-white hover:bg-space-card/60 border border-transparent'
              }`}
            >
              {tab.icon && <span className="text-sm">{tab.icon}</span>}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-mono transition-colors ${
                    isActive
                      ? 'bg-exosignal-cyan text-black font-black'
                      : 'bg-space-card text-exosignal-text-muted border border-exosignal-cyan/20'
                  }`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default SegmentedTabs;
