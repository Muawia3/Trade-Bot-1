import React from 'react';

export const Card = ({
  title,
  subtitle,
  actions,
  children,
  className = '',
  headerClassName = '',
  bodyClassName = '',
  variant = 'default',
  badge = null
}) => {
  const variantStyles = {
    default: 'bg-[#101726]/80 border-slate-800/80',
    highlight: 'bg-[#101726]/90 border-cyan-500/30 shadow-lg shadow-cyan-950/20',
    danger: 'bg-[#101726]/90 border-rose-500/30 shadow-lg shadow-rose-950/20',
    glass: 'glass-panel'
  };

  return (
    <div
      className={`rounded-xl border backdrop-blur-sm transition-all duration-200 overflow-hidden ${
        variantStyles[variant] || variantStyles.default
      } ${className}`}
    >
      {(title || subtitle || actions || badge) && (
        <div
          className={`flex items-center justify-between px-5 py-3.5 border-b border-slate-800/70 bg-slate-900/40 ${headerClassName}`}
        >
          <div className="flex items-center gap-2.5">
            <div>
              {title && (
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-100 tracking-wide">{title}</h3>
                  {badge && <div>{badge}</div>}
                </div>
              )}
              {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </div>
  );
};

export default Card;
