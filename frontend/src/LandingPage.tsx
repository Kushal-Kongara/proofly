import "./LandingPage.css";

interface LandingPageProps {
  onEnterApp: (initialPage?: "dashboard" | "documents" | "o1plan" | "chat" | "updates") => void;
}

export default function LandingPage({ onEnterApp }: LandingPageProps) {
  const scrollToContent = () => {
    const content = document.getElementById("american-dream-story");
    if (content) {
      content.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="ad-landing-root">
      {/* Full Viewport Height Hero (100vh) */}
      <header className="ad-hero-section">
        {/* Left Hero Panel: Royal Blue with Character Artwork */}
        <div className="ad-hero-left">
          <h1 className="ad-brand-title" onClick={() => onEnterApp("dashboard")}>
            Proofly
          </h1>

          <div className="ad-hero-art-container">
            <img
              src="/hero_ad.jpg"
              alt="American Dream Visa Success Character Illustration"
              className="ad-hero-art-img"
            />
          </div>

          <div style={{ color: "rgba(255, 255, 255, 0.85)", fontSize: "0.85rem", fontWeight: 700 }}>
            ✨ Built for Open Atlas 2026 Hackathon
          </div>
        </div>

        {/* Right Hero Panel: Minimalist Editorial Content & Clean Text Nav */}
        <div className="ad-hero-right">
          {/* Minimalist Right Nav Bar */}
          <nav className="ad-nav-bar">
            <button type="button" className="ad-nav-link" onClick={() => onEnterApp("dashboard")}>
              Timeline
            </button>
            <button type="button" className="ad-nav-link" onClick={() => onEnterApp("documents")}>
              Vault
            </button>
            <button type="button" className="ad-nav-link" onClick={() => onEnterApp("o1plan")}>
              O-1 Scorecard
            </button>
            <button type="button" className="ad-nav-link" onClick={() => onEnterApp("updates")}>
              Official Updates
            </button>
            <button type="button" className="ad-nav-link ad-nav-link-accent" onClick={() => onEnterApp("chat")}>
              Ask AI
            </button>
          </nav>

          {/* Hero Content */}
          <div className="ad-hero-main-content">
            <h1 className="ad-hero-h1">
              Empowering Your American Dream.
            </h1>

            <p className="ad-hero-desc">
              Proofly parses your passport, visas, I-20s, I-94s, and EAD cards into a crystal-clear compliance timeline and evaluates your O-1A extraordinary talent evidence with zero hallucinations.
            </p>

            <div className="ad-hero-cta-wrap">
              <button type="button" className="ad-btn-yellow" onClick={() => onEnterApp("dashboard")}>
                <span>Start Your Application</span>
                <span>→</span>
              </button>
            </div>
          </div>

          {/* Hero Bottom Scroll Hint - Centered in Right Panel */}
          <button type="button" className="ad-scroll-hint" onClick={scrollToContent}>
            <span>Scroll down to explore features</span>
            <span>↓</span>
          </button>
        </div>
      </header>

      {/* Checkerboard Split Block 2: O-1 Section */}
      <section id="american-dream-story" className="ad-split-block">
        <div className="ad-split-left-text">
          <span className="ad-badge-tag" style={{ background: "#f3e8ff", color: "#7e22ce" }}>
            GROUNDED AI COPILOT
          </span>

          <h2 className="ad-split-h2">
            Immigration Clarity Grounded in Real Evidence
          </h2>

          <p className="ad-split-quote">
            "Built with Supermemory vector indexing and Featherless RAG, Proofly reads your real uploaded documents to compute status expiration countdowns and evaluate O-1A criteria strength with exact page quote citations."
          </p>

          <div>
            <button
              type="button"
              className="ad-btn-yellow"
              onClick={() => onEnterApp("o1plan")}
              style={{ background: "#d8b4fe" }}
            >
              Evaluate O-1A Criteria →
            </button>
          </div>
        </div>

        <div className="ad-split-right-purple">
          <div className="ad-character-card-wrapper">
            <img
              src="/o1_ad.jpg"
              alt="O-1 Extraordinary Ability Award Character Illustration"
              className="ad-character-art-img"
            />
          </div>
        </div>
      </section>

      {/* Capabilities Grid Section - Colorful Modern Minimal Cards */}
      <section className="ad-capabilities-section">
        <div className="ad-capabilities-header">
          <h2 className="ad-capabilities-h2">Core Platform Capabilities</h2>
        </div>

        <div className="ad-cards-grid">
          {/* Card 1 */}
          <div className="ad-feature-card ad-card-yellow">
            <h3 className="ad-card-h3">Smart Document Vault</h3>
            <p className="ad-card-p">
              Automatic entity & date extraction from passport, visa, I-20, I-94, and EAD cards into a secure vector index.
            </p>
            <button type="button" className="ad-card-action-btn" onClick={() => onEnterApp("documents")}>
              <span>Open Vault</span>
              <span>→</span>
            </button>
          </div>

          {/* Card 2 */}
          <div className="ad-feature-card ad-card-cyan">
            <h3 className="ad-card-h3">Compliance Radar</h3>
            <p className="ad-card-p">
              Deterministic countdown timeline tracking OPT expiration, STEM extension deadlines, grace periods, and status alerts.
            </p>
            <button type="button" className="ad-card-action-btn" onClick={() => onEnterApp("dashboard")}>
              <span>View Timeline</span>
              <span>→</span>
            </button>
          </div>

          {/* Card 3 */}
          <div className="ad-feature-card ad-card-purple">
            <h3 className="ad-card-h3">O-1A Evidence Planner</h3>
            <p className="ad-card-p">
              Assess petition strength across 8 statutory extraordinary criteria (Judging, Awards, Scholarly Papers, Press, Critical Role).
            </p>
            <button type="button" className="ad-card-action-btn" onClick={() => onEnterApp("o1plan")}>
              <span>Score Criteria</span>
              <span>→</span>
            </button>
          </div>

          {/* Card 4 */}
          <div className="ad-feature-card ad-card-green">
            <h3 className="ad-card-h3">Grounded Copilot</h3>
            <p className="ad-card-p">
              Ask any question about your status or evidence. Proofly answers with exact document quote citations and zero hallucinations.
            </p>
            <button type="button" className="ad-card-action-btn" onClick={() => onEnterApp("chat")}>
              <span>Ask Chatbot</span>
              <span>→</span>
            </button>
          </div>

          {/* Card 5 */}
          <div className="ad-feature-card ad-card-rose">
            <h3 className="ad-card-h3">Official Policy Radar</h3>
            <p className="ad-card-p">
              Search live official immigration updates strictly filtered to government domains (USCIS, ICE, State.gov) via Tavily.
            </p>
            <button type="button" className="ad-card-action-btn" onClick={() => onEnterApp("updates")}>
              <span>Search Policy</span>
              <span>→</span>
            </button>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="ad-faq-section">
        <h2 className="ad-capabilities-h2">Frequently Asked Questions</h2>

        <div className="ad-faq-grid">
          <div className="ad-faq-item">
            <h3 className="ad-faq-q">Is Proofly providing legal advice?</h3>
            <p className="ad-faq-a">
              No. Proofly provides informational support and document organization only. It is designed to assist applicants and legal teams in compiling evidence cleanly. Always consult a qualified attorney for formal legal representation.
            </p>
          </div>

          <div className="ad-faq-item">
            <h3 className="ad-faq-q">How does the document-grounded chatbot work?</h3>
            <p className="ad-faq-a">
              Proofly uses Supermemory vector ingestion and Featherless RAG to query your uploaded documents directly. If a document does not contain the answer, Proofly explicitly alerts you rather than hallucinating facts.
            </p>
          </div>

          <div className="ad-faq-item">
            <h3 className="ad-faq-q">What is included in the synthetic demo dataset?</h3>
            <p className="ad-faq-a">
              The public demo is preloaded with the fictional "Maya Patel" profile, tracking a complete transition trajectory from F-1 student status to OPT, STEM OPT, and O-1A petition readiness.
            </p>
          </div>

          <div className="ad-faq-item">
            <h3 className="ad-faq-q">Where do Official Policy Updates come from?</h3>
            <p className="ad-faq-a">
              Policy updates are retrieved via Tavily web search, strictly constrained to verified official US government domain sources (USCIS.gov, ICE.gov, State.gov).
            </p>
          </div>
        </div>
      </section>

      {/* Redesigned Premium Footer Card matching reference mockup */}
      <footer className="ad-footer-section">
        <div className="ad-footer-container">
          <div className="ad-footer-top-grid">
            {/* Col 1 */}
            <div className="ad-footer-col ad-footer-col--main">
              <h3 className="ad-footer-brand-heading">
                Proofly is your grounded immigration compliance & O-1 evidence copilot.
              </h3>
              <p className="ad-footer-disclaimer">
                Informational support only — not legal advice. Built for Open Atlas 2026.
              </p>
            </div>

            {/* Col 2 */}
            <div className="ad-footer-col">
              <span className="ad-footer-col-label">Explore</span>
              <ul className="ad-footer-links">
                <li><button type="button" onClick={() => onEnterApp("dashboard")}>Timeline Dashboard</button></li>
                <li><button type="button" onClick={() => onEnterApp("documents")}>Document Vault</button></li>
                <li><button type="button" onClick={() => onEnterApp("o1plan")}>O-1 Scorecard</button></li>
                <li><button type="button" onClick={() => onEnterApp("updates")}>Official Policy Updates</button></li>
              </ul>
            </div>

            {/* Col 3 */}
            <div className="ad-footer-col">
              <span className="ad-footer-col-label">Technology</span>
              <ul className="ad-footer-links">
                <li><span>Supermemory Index</span></li>
                <li><span>Featherless LLM RAG</span></li>
                <li><span>Tavily Gov Radar</span></li>
                <li><span>Maya Patel Profile</span></li>
              </ul>
            </div>

            {/* Col 4 */}
            <div className="ad-footer-col ad-footer-col--cta">
              <div className="ad-footer-action-item">
                <button type="button" className="ad-footer-cta-link ad-footer-cta-link--yellow" onClick={() => onEnterApp("chat")}>
                  <span>Ask Proofly AI</span>
                  <span className="ad-arrow-circle">↗</span>
                </button>
                <span className="ad-footer-action-sub">Document-grounded Q&A</span>
              </div>

              <div className="ad-footer-action-item">
                <button type="button" className="ad-footer-cta-link ad-footer-cta-link--black" onClick={() => onEnterApp("o1plan")}>
                  <span>O-1 Readiness</span>
                  <span className="ad-arrow-circle">↗</span>
                </button>
                <span className="ad-footer-action-sub">8 Statutory criteria</span>
              </div>
            </div>
          </div>

          {/* Giant Brand Typography Banner */}
          <div className="ad-footer-giant-logo">
            <span>proofly</span>
          </div>

          {/* Bottom Bar */}
          <div className="ad-footer-bottom-bar">
            <span>Proofly © 2026 • Privacy & Legal Disclaimer</span>
            <span>Open Atlas Hackathon 2026 • Grounded AI</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
