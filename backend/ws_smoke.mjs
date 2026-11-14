const base = process.env.WS_SMOKE_BASE || "http://127.0.0.1:8000";
const host = base.replace(/^http/, "ws");

const PASSWORDS = Object.fromEntries(
  ["qzx", "sqx", "yk"].map((username) => {
    const name = `NEXUS_PASSWORD_${username.toUpperCase()}`;
    const password = process.env[name];
    if (!password) throw new Error(`Missing ${name}`);
    return [username, password];
  }),
);

async function login(username) {
  const response = await fetch(`${base}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password: PASSWORDS[username] }),
  });
  if (!response.ok) throw new Error(`login failed: ${response.status}`);
  return (await response.json()).token;
}

function connect(token) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(`${host}/ws/chat/`, {
      protocols: ["zixxx.chat", `token.${token}`],
      headers: { Origin: base },
    });
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    socket.addEventListener("open", () => {
      clearTimeout(timer);
      resolve(socket);
    });
    socket.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("socket error"));
    });
  });
}

const [qzToken, suToken, ykToken] = await Promise.all([
  login("qzx"),
  login("sqx"),
  login("yk"),
]);

const qz = await connect(qzToken);
const su = await connect(suToken);
const text = `ws smoke ${Date.now()}`;

const received = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("message timeout")), 5000);
  su.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "message" && data.message.content === text) {
      clearTimeout(timer);
      resolve(data.message);
    }
  });
});

qz.send(JSON.stringify({ type: "message.send", content: text }));
const message = await received;
console.log("received", message.sender_username, message.content);

const typing = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("typing timeout")), 5000);
  su.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "typing" && data.username === "qzx") {
      clearTimeout(timer);
      resolve(data);
    }
  });
});
qz.send(JSON.stringify({ type: "typing", is_typing: true }));
console.log("typing", await typing);

qz.close();
su.close();

await new Promise((resolve) => {
  const socket = new WebSocket(`${host}/ws/chat/`, {
    protocols: ["zixxx.chat", `token.${ykToken}`],
    headers: { Origin: base },
  });
  socket.addEventListener("error", () => {});
  socket.addEventListener("close", (event) => {
    console.log("yk closed", event.code);
    resolve();
  });
  socket.addEventListener("open", () => {
    console.log("ERROR: yk unexpectedly connected");
    process.exitCode = 1;
    socket.close();
  });
});

console.log("websocket checks passed");
