const nodemailer = require("nodemailer");
const fs = require("fs");
const path = require("path");

const EMAIL_PROVIDER_MODE = process.env.EMAIL_PROVIDER_MODE || "smtp";

let transporter = null;

function createTransporter() {
  if (EMAIL_PROVIDER_MODE === "mock") {
    return {
      sendMail: async (opts) => {
        console.log("[mock mail] to=", opts.to);
        return { accepted: [opts.to] };
      },
    };
  }

  transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT || 587),
    secure: String(process.env.SMTP_SECURE) === "true",
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASSWORD,
    },
  });

  return transporter;
}

function loadTemplate(name) {
  const file = path.join(__dirname, "templates", name);
  return fs.readFileSync(file, "utf-8");
}

async function sendOtpEmail({ to, student_name, otp }) {
  const transport = createTransporter();
  const html = loadTemplate("otp-email.html").replace(/\{\{name\}\}/g, student_name).replace(/\{\{otp\}\}/g, otp).replace(/\{\{minutes\}\}/g, process.env.OTP_EXPIRY_MINUTES || "10");
  const text = `Hello ${student_name},\n\nYour verification OTP is: ${otp}\nThis OTP is valid for ${process.env.OTP_EXPIRY_MINUTES || "10"} minutes.\n\nIf you did not request this, please ignore this email.`;

  const mailOptions = {
    from: process.env.EMAIL_FROM,
    to,
    subject: "VSIT Student Assistant - Email Verification OTP",
    text,
    html,
  };

  return transport.sendMail(mailOptions);
}

module.exports = { sendOtpEmail };
