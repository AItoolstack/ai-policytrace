/** ai·toolstack brand primitives shared by every PolicyTrace screen. */

export function Mark({ size = 24 }: { size?: number }) {
  // Three layers of a system; the middle one ends in an amber dot: a value traced to its source.
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="#1F2940" />
      <rect x="7" y="7.5" width="18" height="3" rx="1.5" fill="#8A93A8" />
      <rect x="7" y="14.5" width="11" height="3" rx="1.5" fill="#F6F5F1" />
      <circle cx="23.5" cy="16" r="2.4" fill="#E0A946" />
      <rect x="7" y="21.5" width="18" height="3" rx="1.5" fill="#8A93A8" />
    </svg>
  )
}
export function Lockup({ product = 'PolicyTrace' }: { product?: string }) {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <a
        href="https://www.ai-toolstack.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 text-ink-100"
        aria-label="ai·toolstack home"
      >
        <Mark size={24} />
        <span className="text-[17px] font-semibold tracking-[-0.02em] hidden sm:inline">
          ai<span className="text-signal-deep">·</span>toolstack
        </span>
      </a>
      <span className="text-ink-600 select-none hidden sm:inline" aria-hidden="true">/</span>
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink-100 truncate">{product}</span>
    </div>
  )
}

export function ExternalIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </svg>
  )
}

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z" />
    </svg>
  )
}

export const LINKS = {
  chapters: 'https://www.ai-toolstack.com/projects/policytrace/',
  github: 'https://github.com/AItoolstack/ai-policytrace',
}
