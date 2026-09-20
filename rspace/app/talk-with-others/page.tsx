"use client"

import SiteHeader from "@/app/components/SiteHeader";
import { useState } from "react";

type User = {
  givenName: string,
  surname: string,
  pfp: string,
}

type Message = {
  text: string,
  sent: Date,
  read: boolean,
  fromMe: boolean,
}

type Chat = {
  user: User,
  messages: Message[],
}

const chats: Chat[] = [
  {
    user: { givenName: "Margaret", surname: "Chen", pfp: "MC" },
    messages: [
      { text: "Good morning! Did you try that lemon cake recipe?", sent: new Date("2026-09-19T13:12:00.000Z"), read: true, fromMe: false },
      { text: "I did — it turned out lovely. I saved you a slice.", sent: new Date("2026-09-19T13:18:00.000Z"), read: true, fromMe: true },
      { text: "You're a gem. I'll stop by after the garden club.", sent: new Date("2026-09-19T13:21:00.000Z"), read: true, fromMe: false },
      { text: "Bring your walking shoes. We can go around the pond.", sent: new Date("2026-09-19T13:24:00.000Z"), read: true, fromMe: true },
    ],
  },
  {
    user: { givenName: "Harold", surname: "Brooks", pfp: "HB" },
    messages: [
      { text: "Are we still on for chess on Thursday?", sent: new Date("2026-09-18T20:04:00.000Z"), read: true, fromMe: false },
      { text: "Yes — library at 2. I'll bring the board.", sent: new Date("2026-09-18T20:07:00.000Z"), read: true, fromMe: true },
      { text: "Perfect. I've been practicing my Sicilian Defense.", sent: new Date("2026-09-18T20:11:00.000Z"), read: false, fromMe: false },
    ],
  },
  {
    user: { givenName: "Priya", surname: "Nair", pfp: "PN" },
    messages: [
      { text: "That documentary last night was wonderful.", sent: new Date("2026-09-18T00:41:00.000Z"), read: true, fromMe: false },
      { text: "The birds over the marsh? I teared up a little.", sent: new Date("2026-09-18T00:45:00.000Z"), read: true, fromMe: true },
      { text: "Same here. Let's watch the next one together.", sent: new Date("2026-09-18T00:48:00.000Z"), read: true, fromMe: false },
    ],
  },
  {
    user: { givenName: "Luis", surname: "Ortega", pfp: "LO" },
    messages: [
      { text: "The community choir is looking for tenors.", sent: new Date("2026-09-16T15:02:00.000Z"), read: true, fromMe: false },
      { text: "Tempting! When do they rehearse?", sent: new Date("2026-09-16T15:15:00.000Z"), read: true, fromMe: true },
      { text: "Tuesdays at 6 in the rec hall. Coffee after.", sent: new Date("2026-09-16T15:17:00.000Z"), read: true, fromMe: false },
      { text: "I'll come try it this week.", sent: new Date("2026-09-16T15:20:00.000Z"), read: true, fromMe: true },
    ],
  },
  {
    user: { givenName: "Franklin", surname: "Zhu", pfp: "FZ" },
    messages: [
      { text: "I'm attending HackMIT 2026.", sent: new Date("2026-09-16T15:02:00.000Z"), read: false, fromMe: false },
      { text: "I'm currently writing this at 6:38 AM...pretty tired", sent: new Date("2026-09-16T15:15:00.000Z"), read: false, fromMe: false },
      { text: "Gonna go finish up the UI.", sent: new Date("2026-09-16T15:17:00.000Z"), read: false, fromMe: false },
      { text: "See you later", sent: new Date("2026-09-16T15:20:00.000Z"), read: false, fromMe: false },
    ],
  },
];

function formatTime(date: Date) {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

function lastMessage(chat: Chat) {
  return chat.messages[chat.messages.length - 1];
}

export default function TalkWithOthersPage() {
  const [selectedChat, setSelectedChat] = useState<number>(0);
  const activeChat = chats[selectedChat];

  const handleChatSelection = (index: number) => {
    setSelectedChat(index);
    chats[index].messages = chats[index].messages.map((message) => {
      message.read = true;
      return message;
    });
  }

  return (
    <main className="flex flex-col min-h-screen bg-[var(--sky)]">
      <SiteHeader />
      <main className="flex flex-col my-8 w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-8">
          <div className="flex flex-row justify-between">
            <h1 className="text-6xl font-bold">Talk with Others</h1>
            <button className="self-end p-5 rounded-2xl text-lg font-bold bg-(--lemon)">
              Match me with a new friend!
            </button>
          </div>
          <div className="flex flex-row w-full h-200 overflow-hidden rounded-2xl">
            <div className="flex flex-1 flex-col overflow-y-auto rounded-l-2xl bg-gray-100">
              <div className="flex items-center gap-3 font-semibold text-2xl border-b border-black/10 bg-white/60 px-5 py-3 h-20">
                <img
                  src="/speechbubble.svg"
                  alt="Speech bubble icon"
                  className="size-7.5 mx-1.5"
                />
                Conversations
              </div>
              {chats.map((chat, index) => {
                const latest = lastMessage(chat);
                const unreadCount = chat.messages
                  .map((message) => +(!message.read && !message.fromMe))
                  .reduce((acc, cur) => acc += cur);
                const selected = index === selectedChat;

                return (
                  <button
                    key={`${chat.user.givenName}-${chat.user.surname}`}
                    type="button"
                    className={`p-4 flex w-full items-center gap-3 border-b border-black/5 px-4 py-3 text-left ${selected ? "bg-white" : "bg-transparent hover:bg-white/70"}`}
                    onClick={() => handleChatSelection(index)}
                    aria-pressed={selected}
                  >
                    <span className="grid size-12 shrink-0 place-items-center rounded-full bg-[var(--periwinkle)] font-bold text-[var(--ink)]">
                      {chat.user.pfp}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="truncate font-bold text-[var(--ink)]">
                          {chat.user.givenName} {chat.user.surname}
                        </span>
                        <span className="shrink-0 text-xs text-black/50">
                          {formatTime(latest.sent)}
                        </span>
                      </span>
                      <span className={`mt-0.5 block truncate text-sm ${unreadCount > 0 ? "font-bold text-[var(--ink)]" : "text-black/55"}`}>
                        {latest.fromMe ? "You: " : ""}{unreadCount <= 1 ? latest.text : `${unreadCount} new messages`}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="flex flex-2 flex-col rounded-r-2xl bg-gray-200">
              <div className="flex items-center gap-3 border-b border-black/10 bg-white/60 px-5 py-3 h-20">
                <span className="grid size-11 place-items-center rounded-full bg-[var(--periwinkle)] font-bold text-[var(--ink)]">
                  {activeChat.user.pfp}
                </span>
                <div>
                  <p className="font-bold text-[var(--ink)]">
                    {activeChat.user.givenName} {activeChat.user.surname}
                  </p>
                  <p className="text-sm text-black/50">Active now</p>
                </div>
              </div>
              <div className="p-4 flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-4">
                {activeChat.messages.map((message) => (
                  <div
                    key={`${message.sent.toISOString()}-${message.text}`}
                    className={`flex ${message.fromMe ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[72%] rounded-[1.4rem] px-4 py-2.5 text-[var(--ink)] ${message.fromMe ? "rounded-br-md bg-[var(--periwinkle)]/67" : "rounded-bl-md bg-white"}`}
                    >
                      <p>{message.text}</p>
                      <p className={`mt-1 text-xs text-black/45 ${message.fromMe ? "text-right" : "text-left"}`}>
                        {formatTime(message.sent)}
                        {message.fromMe ? (message.read ? " · Seen" : " · Sent") : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              <form
                className="flex gap-2 border-t border-black/10 bg-white/60 px-4 py-3"
                onSubmit={(event) => event.preventDefault()}
              >
                <input
                  className="min-h-12 flex-1 rounded-full border-[3px] border-[var(--ink)] bg-white px-4 outline-none focus:outline-4 focus:outline-offset-2 focus:outline-[var(--lemon)]"
                  type="text"
                  placeholder={`Message ${activeChat.user.givenName}…`}
                  aria-label={`Message ${activeChat.user.givenName}`}
                />
                <button
                  className="rounded-full bg-[var(--lemon)] px-5 font-bold"
                  type="submit"
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        </section>
      </main>
    </main>
  );
}
