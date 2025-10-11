import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="container">
      <header>
        <h1>FoldIt Web</h1>
        <p>Collaborative protein folding challenges in your browser.</p>
      </header>
      <section>
        <p>
          This is the early scaffold for the FoldIt web client. Explore the
          design notes, test out the interface, and help us iterate on the
          experience.
        </p>
        <div className="landing-actions">
          <Link className="cta" href="/play">
            Quick Play
          </Link>
          <Link className="cta secondary" href="/levels">
            Browse Levels
          </Link>
        </div>
      </section>
    </main>
  );
}
