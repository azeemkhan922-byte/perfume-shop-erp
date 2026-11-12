import { Component } from "react";

// Shows a readable message instead of a blank white page if a screen crashes.
export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="login-page">
        <div className="login-card">
          <div className="brand">AZEEM FRAGRANCES</div>
          <div className="gold-rule" />
          <div className="error" role="alert">Something went wrong: {String(this.state.error.message || this.state.error)}</div>
          <button onClick={() => { this.props.onReset?.(); this.setState({ error: null }); }}>{this.props.resetLabel || "Back to sign in"}</button>
        </div>
      </main>
    );
  }
}
