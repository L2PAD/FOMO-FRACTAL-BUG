import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function LegalPage() {
  const { pageType } = useParams();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/legal/${pageType}`)
      .then(r => r.json())
      .then(data => { if (data.ok) setPage(data.page); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [pageType]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white" style={{ fontFamily: "'Gilroy', sans-serif" }}
      data-testid={`legal-page-${pageType}`}>
      <div className="max-w-3xl mx-auto px-6 sm:px-8 py-16">
        <Link to="/info" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-10"
          data-testid="legal-back-link">
          <ArrowLeft className="w-4 h-4" /> Back to home
        </Link>

        <h1 className="text-3xl sm:text-4xl font-medium tracking-tight mb-8" data-testid="legal-title">
          {page?.title || (pageType === 'terms' ? 'Terms of Service' : 'Privacy Policy')}
        </h1>

        <div className="prose prose-invert prose-zinc max-w-none text-zinc-400 leading-relaxed text-[15px] whitespace-pre-wrap"
          data-testid="legal-content">
          {page?.content || 'Content not available.'}
        </div>
      </div>
    </div>
  );
}
