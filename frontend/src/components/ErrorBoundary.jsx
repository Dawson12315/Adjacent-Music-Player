import { Component } from "react";

/**
 * A page that throws while rendering used to unmount the whole app, the
 * player and its audio element included, leaving a blank screen with the
 * music stopped. This catches it at the page: the sidebar, the player bar
 * and the music stay, and the page says what happened and offers Home.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Page failed to render", error, info?.componentStack);
  }

  componentDidUpdate(previousProps) {
    // A new location is a fresh attempt.
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="state-message" role="alert">
        <h2>This page could not be shown.</h2>
        <p>The rest of Adjacent is still here, and the music keeps playing.</p>
        <a className="button" href="/">
          Go to Home
        </a>
      </div>
    );
  }
}
