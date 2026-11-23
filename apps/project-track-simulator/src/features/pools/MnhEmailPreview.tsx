import type { MnhEmailDraft } from "../../lib/mnhEmailTemplate";

export function MnhEmailPreview({ draft, recorded }: { draft: MnhEmailDraft; recorded?: boolean }) {
  return (
    <div className="rv-mnh-email">
      {recorded ? (
        <p className="rv-mnh-email__notice rv-mnh-email__notice--sent" role="status">
          Mock email sent: this message is stored and marked as delivered in the simulator. SMTP is not used yet; HR and
          Cc were recorded for a future mail integration.
        </p>
      ) : (
        <p className="rv-mnh-email__notice rv-mnh-email__notice--preview">
          Review the email below. Nothing is sent yet — confirm to record the MyNextHire request.
        </p>
      )}
      <dl className="rv-mnh-email__headers">
        <div className="rv-mnh-email__row">
          <dt>To</dt>
          <dd>{draft.to}</dd>
        </div>
        <div className="rv-mnh-email__row">
          <dt>Cc</dt>
          <dd>{draft.cc}</dd>
        </div>
        <div className="rv-mnh-email__row rv-mnh-email__row--subject">
          <dt>Subject</dt>
          <dd>{draft.subject}</dd>
        </div>
      </dl>
      <pre className="rv-mnh-email__body" tabIndex={0}>
        {draft.body_text}
      </pre>
    </div>
  );
}