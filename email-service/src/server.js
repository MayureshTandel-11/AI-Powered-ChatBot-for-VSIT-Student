require('dotenv').config();
const express = require('express');
const morgan = require('morgan');
const bodyParser = require('body-parser');

const { sendOtpEmail } = require('./mailer');

const app = express();
app.use(morgan('dev'));
app.use(bodyParser.json());

app.post('/send-otp', async (req, res) => {
  const { email, student_name, otp } = req.body;
  if (!email || !otp) {
    return res.status(400).json({ success: false, message: 'Missing email or otp' });
  }

  try {
    await sendOtpEmail({ to: email, student_name: student_name || 'Student', otp });
    return res.json({ success: true, message: 'OTP email sent successfully' });
  } catch (err) {
    console.error('Failed to send email', err);
    return res.status(502).json({ success: false, message: 'Failed to send email' });
  }
});

app.get('/health', (req, res) => {
  res.json({ ok: true });
});

const port = process.env.PORT || 3001;
app.listen(port, () => console.log(`Email service listening on ${port}`));
