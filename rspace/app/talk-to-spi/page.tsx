"use client"

import SiteHeader from "@/app/components/SiteHeader";
import { SquigglyBorders } from "@/app/components/SquigglyBorders";
import { useState } from "react";

type Message = {
  text: string,
  sent: Date,
  fromMe: boolean,
}

type Conversation = {
  id: string,
  title: string,
  messages: Message[],
}

const conversations: Conversation[] = [
  {
    id: "garden-planning",
    title: "Garden Planning",
    messages: [
      { text: "Hello! I'm Spi, your AI assistant. How can I help you today?", sent: new Date("2026-09-20T10:00:00.000Z"), fromMe: false },
      { text: "Hi Spi! Can you help me plan a garden?", sent: new Date("2026-09-20T10:05:00.000Z"), fromMe: true },
      { text: "Of course! I'd love to help you plan a garden. What size space are you working with, and what type of plants are you interested in growing?", sent: new Date("2026-09-20T10:06:00.000Z"), fromMe: false },
      { text: "I have a small backyard, about 20x30 feet. I'd like to grow vegetables and some herbs.", sent: new Date("2026-09-20T10:10:00.000Z"), fromMe: true },
      { text: "That's a wonderful size for a vegetable garden! For a 20x30 space, I'd recommend: 1) raised beds for vegetables (tomatoes, peppers, lettuce), 2) a herb garden near the kitchen door (basil, rosemary, thyme), and 3) some vertical growing for cucumbers or beans. Would you like me to create a detailed layout plan?", sent: new Date("2026-09-20T10:12:00.000Z"), fromMe: false },
    ],
  },
  {
    id: "recipe-help",
    title: "Recipe Help",
    messages: [
      { text: "I need help with a dinner recipe for tonight.", sent: new Date("2026-09-19T18:30:00.000Z"), fromMe: true },
      { text: "I'd be happy to help! What ingredients do you have on hand, and do you have any dietary restrictions or preferences?", sent: new Date("2026-09-19T18:31:00.000Z"), fromMe: false },
      { text: "I have chicken, vegetables, and some basic pantry staples. No restrictions, just something quick and healthy.", sent: new Date("2026-09-19T18:33:00.000Z"), fromMe: true },
      { text: "Perfect! How about a quick chicken stir-fry? You can slice the chicken, stir-fry it with your vegetables, and season with soy sauce, garlic, and ginger. It takes about 15 minutes and is very healthy!", sent: new Date("2026-09-19T18:35:00.000Z"), fromMe: false },
    ],
  },
  {
    id: "travel-planning",
    title: "Travel Planning",
    messages: [
      { text: "I'm planning a weekend trip to the mountains. Any suggestions?", sent: new Date("2026-09-18T14:00:00.000Z"), fromMe: true },
      { text: "That sounds lovely! What activities are you interested in? Hiking, relaxation, or adventure sports?", sent: new Date("2026-09-18T14:02:00.000Z"), fromMe: false },
      { text: "Mostly hiking and relaxation. Maybe some photography too.", sent: new Date("2026-09-18T14:05:00.000Z"), fromMe: true },
      { text: "Great choice! I'd recommend finding a cabin with mountain views, planning 2-3 moderate hikes, and bringing a good camera for sunrise/sunset shots. Don't forget to pack layers – mountain weather can change quickly!", sent: new Date("2026-09-18T14:08:00.000Z"), fromMe: false },
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

function lastMessage(conversation: Conversation) {
  return conversation.messages[conversation.messages.length - 1];
}

export default function TalkToSpiPage() {
  const [selectedConversation, setSelectedConversation] = useState<number>(0);
  const [conversationList, setConversationList] = useState<Conversation[]>(conversations);
  const activeConversation = conversationList[selectedConversation];

  const handleConversationSelection = (index: number) => {
    setSelectedConversation(index);
  }

  const handleSendMessage = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector('input') as HTMLInputElement;
    const text = input.value.trim();
    
    if (!text) return;

    const newMessage: Message = {
      text,
      sent: new Date(),
      fromMe: true,
    };

    const updatedConversations = [...conversationList];
    updatedConversations[selectedConversation].messages = [
      ...updatedConversations[selectedConversation].messages,
      newMessage,
    ];
    setConversationList(updatedConversations);
    input.value = '';
  }

  const handleNewConversation = () => {
    const newConversation: Conversation = {
      id: `conversation-${Date.now()}`,
      title: "New Conversation",
      messages: [
        { text: "Hello! I'm Spi, your AI assistant. How can I help you today?", sent: new Date(), fromMe: false },
      ],
    };
    setConversationList([newConversation, ...conversationList]);
    setSelectedConversation(0);
  }

  return (
    <main className="flex flex-col min-h-screen bg-[var(--sky)]">
      <SquigglyBorders />
      <SiteHeader />
      <main className="flex flex-col my-8 w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-8">
          <div className="flex flex-row justify-between">
            <div className="flex flex-row gap-4 justify-items-center">
              <h1 className="animate-fade-in text-6xl font-bold">Talk to Spi</h1>
              <img
                src="/spi.svg"
                alt="Spi logo"
                className="size-15"
              />
            </div>
            <button 
              className="animate-fade-in-delay0.5s self-end px-9 py-5 text-lg font-bold bg-(--lemon) shadow-md"
              onClick={handleNewConversation}
              style={{ clipPath: "url(#squiggly-button)" }}
            >
              Start new conversation
            </button>
          </div>
          <div className="animate-fade-in-delay0.5s flex flex-row w-full h-200 overflow-hidden rounded-2xl">
            <div className="flex flex-1 flex-col overflow-y-auto rounded-l-2xl bg-gray-100">
              <div className="flex items-center gap-3 font-semibold text-2xl border-b border-black/10 bg-white/60 px-5 py-3 h-20">
                <img
                  src="/speechbubble.svg"
                  alt="Speech bubble icon"
                  className="size-7.5 mx-1.5"
                />
                <div className="flex flex-col">
                  <p>Conversations</p>
                  <p className="text-[10px] text-gray-700">Click a topic below to view its conversation</p>
                </div>
              </div>
              {conversationList.map((conversation, index) => {
                const latest = lastMessage(conversation);
                const selected = index === selectedConversation;

                return (
                  <button
                    key={conversation.id}
                    type="button"
                    className={`p-4 flex w-full items-center gap-3 border-b border-black/5 px-4 py-3 text-left ${selected ? "bg-linear-to-r from-white via-67 via-white to-gray-200" : "bg-transparent hover:bg-white/70"}`}
                    onClick={() => handleConversationSelection(index)}
                    aria-pressed={selected}
                  >
                    <span className="grid size-12 shrink-0 place-items-center rounded-full bg-[var(--periwinkle)] font-bold text-[var(--ink)]">
                      Spi
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="truncate font-bold text-[var(--ink)]">
                          {conversation.title}
                        </span>
                        <span className="shrink-0 text-xs text-black/50">
                          {formatTime(latest.sent)}
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate text-sm text-black/55">
                        {latest.fromMe ? "You: " : "Spi: "}{latest.text}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="flex flex-2 flex-col rounded-r-2xl bg-gray-200">
              <div className="flex items-center gap-3 border-b border-black/10 bg-white/60 px-5 py-3 h-20">
                <span className="grid size-11 place-items-center rounded-full bg-[var(--periwinkle)] font-bold text-[var(--ink)]">
                  Spi
                </span>
                <div>
                  <p className="font-bold text-[var(--ink)]">
                    Spi AI Assistant
                  </p>
                  <p className="text-sm text-black/50">Always here to help</p>
                </div>
              </div>
              <div className="p-4 flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-4">
                {activeConversation.messages.map((message) => (
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
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              <form
                className="flex gap-2 border-t border-black/10 bg-white/60 px-4 py-3"
                onSubmit={handleSendMessage}
              >
                <input
                  className="min-h-12 flex-1 rounded-full border-[3px] border-[var(--ink)] bg-white px-4 outline-none focus:outline-4 focus:outline-offset-2 focus:outline-[var(--lemon)]"
                  type="text"
                  placeholder="Message Spi…"
                  aria-label="Message Spi"
                />
                <button
                  className="bg-[var(--lemon)] px-9 py-2 font-bold shadow-md"
                  type="submit"
                  style={{ clipPath: "url(#squiggly-button)" }}
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
