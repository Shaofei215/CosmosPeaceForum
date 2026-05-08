import { useEffect, useState } from 'react';
import { ChevronUp } from 'lucide-react';

const SHOW_THRESHOLD = 320;

export function BackToTopButton() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsVisible(window.scrollY >= SHOW_THRESHOLD);
    };

    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  const handleBackToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  return (
    <div
      className={`transition-all duration-200 ${
        isVisible ? 'translate-y-0 opacity-100' : 'pointer-events-none -translate-y-1 opacity-0'
      }`}
    >
      <button
        type="button"
        onClick={handleBackToTop}
        aria-label="回到顶部"
        className="flex h-12 w-12 items-center justify-center rounded-lg bg-white shadow-sm transition-colors hover:bg-muted/40"
      >
        <ChevronUp className="h-5 w-5 text-foreground" />
      </button>
    </div>
  );
}
