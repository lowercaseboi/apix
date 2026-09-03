import Dashboard from "./Dashboard";
import Landing from "./Landing";
import { API_BASE, useApiData } from "./hooks";
import "./App.css";

export default function App() {
  const { data, error } = useApiData();

  return (
    <>
      <div className="aurora" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <div className="app">
        <nav className="nav">
          <div className="container nav-inner">
            <div className="brand">
              <span className="brand-mark">✈</span>
              APIx
            </div>
            <div className="nav-links">
              <a href="#why">Why</a>
              <a href="#how">How it works</a>
              <a href="#dashboard">Live index</a>
            </div>
            <a className="btn btn-ghost" href="#dashboard" style={{ padding: "0.5rem 1rem", fontSize: "0.82rem" }}>
              View index
            </a>
          </div>
        </nav>

        <Landing data={data} />

        {error ? (
          <div className="container" style={{ paddingBottom: "4rem" }}>
            <div className="err">
              <b>Could not reach the API.</b> {error}
              <br />
              Start it with <code>uvicorn src.api:app --reload</code>, then reload this page. Expected
              at <code>{API_BASE}</code>.
            </div>
          </div>
        ) : !data ? (
          <div className="container" style={{ paddingBottom: "4rem" }}>
            <div className="skeleton" />
          </div>
        ) : (
          <Dashboard data={data} />
        )}

        <footer>
          <div className="container">
            <b>APIx</b> — automated daily airfare price index · SIH 2026, PS 26056 · built for
            MoSPI&apos;s Data Informatics &amp; Innovation Division.
            <br />
            Anomaly detection is a z-score; the projection is an OLS baseline. Neither is machine
            learning, and the current index runs on a labelled synthetic panel.
          </div>
        </footer>
      </div>
    </>
  );
}
