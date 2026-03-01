"""
Tools used by graph nodes — each module has a single responsibility.

  - data_lookup: Policy lookup by number (Intake).
  - cancellation_rules: Eligibility check (Analysis, Refund).
  - refund_calculator: Refund amount computation (Refund).
  - refund_logger: Append approved refunds to CSV (Log Refund).
  - notice_generator: Generate cancellation notice PDF (Summary).

See agent_roles.TOOL_RESPONSIBILITIES for used_by mapping.
"""
