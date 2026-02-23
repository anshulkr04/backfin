"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";

const SOCKET_URL = "https://api.marketwire.ai";

export function useNewAnnouncementSocket() {
  const socketRef = useRef<Socket | null>(null);
  const [newCount, setNewCount] = useState(0);

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 3000,
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("[Socket.IO] Connected:", socket.id);
    });

    socket.on("new_announcement", () => {
      setNewCount((prev) => prev + 1);
    });

    socket.on("disconnect", (reason) => {
      console.log("[Socket.IO] Disconnected:", reason);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  const resetCount = useCallback(() => {
    setNewCount(0);
  }, []);

  return { newCount, resetCount };
}
