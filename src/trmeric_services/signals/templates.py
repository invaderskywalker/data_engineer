FY27_DEMAND_KICKOFF_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FY27 Demand Kickoff</title>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:Arial, sans-serif;">

  <div style="max-width:600px; margin:0 auto; background:#ffffff;">

    <!-- HEADER -->
    <div style="background:#FF6B00; padding:28px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:20px; font-weight:700; color:#ffffff;">trmeric</td>
          <td align="right" style="font-size:12px; color:rgba(255,255,255,0.8);">FY27 · Demand Submission</td>
        </tr>
      </table>
    </div>

    <!-- BODY -->
    <div style="padding:36px;">

      <p style="font-size:15px; color:#111111; margin:0 0 24px;">Hi <strong>{user_name}</strong>,</p>

      <p style="font-size:14px; color:#444444; line-height:1.7; margin:0 0 28px;">
        You have <strong style="color:#FF6B00;">{demand_count} draft FY27 demands</strong> waiting for your review and submission. Please go through each one and submit before the deadline to ensure your demands are included in FY27 planning.
      </p>

      <!-- Demand list -->
      <div style="border:1px solid #e8e8e8; border-radius:8px; padding:20px 24px; margin-bottom:28px;">
        <div style="font-size:11px; font-weight:700; color:#FF6B00; text-transform:uppercase; letter-spacing:1px; margin-bottom:14px;">
          Draft Demands to be reviewed and submitted
        </div>
        {demand_lines}
      </div>

      <!-- Deadline callout -->
      <div style="border-left:3px solid #FF6B00; padding:14px 18px; background:#fafafa; border-radius:0 6px 6px 0; margin-bottom:32px;">
        <span style="font-size:13px; color:#444;">Submission deadline: </span>
        <strong style="font-size:13px; color:#111;">{deadline}</strong>
      </div>

      <!-- CTA button -->
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:#FF6B00; border-radius:6px; padding:12px 28px;">
            <a href="https://trmeric.com/actionhub" style="color:#ffffff; font-size:13px; font-weight:700; text-decoration:none;">
              Review My Demands →
            </a>
          </td>
        </tr>
      </table>

    </div>

    <!-- FOOTER -->
    <div style="border-top:1px solid #eeeeee; padding:20px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:11px; color:#aaaaaa;">trmeric · The New Way to Tech</td>
          <td align="right" style="font-size:11px; color:#aaaaaa;">©2026 trmeric Inc</td>
        </tr>
      </table>
    </div>

  </div>
</body>
</html>
"""


FY27_ZERO_DEMAND_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FY27 Demand Reminder</title>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:Arial, sans-serif;">

  <div style="max-width:600px; margin:0 auto; background:#ffffff;">

    <!-- HEADER -->
    <div style="background:#FF6B00; padding:28px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:20px; font-weight:700; color:#ffffff;">trmeric</td>
          <td align="right" style="font-size:12px; color:rgba(255,255,255,0.8);">FY27 · Demand Submission</td>
        </tr>
      </table>
    </div>

    <!-- BODY -->
    <div style="padding:36px;">

      <p style="font-size:15px; color:#111111; margin:0 0 24px;">Hi <strong>{user_name}</strong>,</p>

      <p style="font-size:14px; color:#444444; line-height:1.7; margin:0 0 28px;">
        We noticed you haven't submitted any FY27 demands yet. Submitting on time ensures your demands are included in FY27 planning.
      </p>

      <!-- Status callout -->
      <div style="border:1px solid #e8e8e8; border-radius:8px; padding:20px 24px; margin-bottom:28px;">
        <div style="font-size:13px; color:#888888; margin-bottom:4px;">Demands submitted</div>
        <div style="font-size:28px; font-weight:700; color:#FF6B00; letter-spacing:-1px;">0</div>
      </div>

      <!-- Deadline callout -->
      <div style="border-left:3px solid #FF6B00; padding:14px 18px; background:#fafafa; border-radius:0 6px 6px 0; margin-bottom:32px;">
        <span style="font-size:13px; color:#444;">Submission deadline: </span>
        <strong style="font-size:13px; color:#111;">{deadline}</strong>
      </div>

      <!-- CTA button -->
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:#FF6B00; border-radius:6px; padding:12px 28px;">
            <a href="https://trmeric.com/actionhub" style="color:#ffffff; font-size:13px; font-weight:700; text-decoration:none;">
              Submit My Demands →
            </a>
          </td>
        </tr>
      </table>

    </div>

    <!-- FOOTER -->
    <div style="border-top:1px solid #eeeeee; padding:20px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:11px; color:#aaaaaa;">trmeric · The New Way to Tech</td>
          <td align="right" style="font-size:11px; color:#aaaaaa;">©2026 trmeric Inc</td>
        </tr>
      </table>
    </div>

  </div>
</body>
</html>
"""
