import Link from "next/link";

export default function PlayPage() {
  return (
    <main className="container">
      <header>
        <h1>Play FoldIt</h1>
        <p>Interactive folding workspace coming soon.</p>
      </header>
      <section>
        <p>
          The game UI will render here. For now, this placeholder confirms that
          routing and layout are wired up for future development.
        </p>
        <Link href="/">Return to landing</Link>
      </section>
    </main>
  );
}
