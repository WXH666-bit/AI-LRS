import type { GameEvent } from "./types";

const ROLE_LABELS: Record<string, string> = {
  wolf: "狼人",
  seer: "预言家",
  witch: "女巫",
  hunter: "猎人",
  guard: "守卫",
  villager: "平民",
};

export const PHASE_LABELS: Record<string, string> = {
  lobby: "房间准备",
  night: "夜晚",
  sheriff_election: "警长竞选",
  night_result: "公布夜间结果",
  day_speech: "白天发言",
  lynch_vote: "放逐投票",
  lynch_pk_speech: "平票PK发言",
  lynch_pk_vote: "平票PK投票",
  hunter_shot: "猎人开枪",
  sheriff_transfer: "警徽移交",
  last_words: "遗言",
  ended: "对局结束",
};

export function roleLabel(role: string | null | undefined): string {
  return role ? ROLE_LABELS[role] || role : "";
}

export interface DisplayLine {
  text: string;
  kind: "phase" | "public" | "wolf" | "private" | "death" | "system" | "me";
  seq: number;
}

const DEATH_MODES: Record<string, string> = {
  wolf: "被狼人击杀",
  poison: "被女巫毒杀",
  lynch: "被放逐",
  explode: "自爆",
  hunter: "被猎人开枪",
};

export function formatEvent(ev: GameEvent): DisplayLine | null {
  const { type, payload, actor_seat: actor, seq, day, night } = ev;
  const P = payload;

  switch (type) {
    case "game_started":
      return { text: `游戏开始（${P.board_size}人局）`, kind: "system", seq };
    case "phase_change": {
      const label = PHASE_LABELS[P.phase] || P.phase;
      const prefix = P.phase === "night" ? `第 ${P.night} 夜` : `第 ${P.day} 天`;
      return { text: `—— ${prefix} · ${label} ——`, kind: "phase", seq };
    }
    case "role_assign":
      return { text: `你的身份：${ROLE_LABELS[P.role] || P.role}`, kind: "private", seq };
    case "speech":
      return P.skipped
        ? { text: `${actor}号（跳过发言）`, kind: "public", seq }
        : { text: `【${actor}号】${P.text}`, kind: "public", seq };
    case "last_words":
      return P.skipped
        ? { text: `${actor}号遗言（跳过）`, kind: "public", seq }
        : { text: `💀 【${actor}号遗言】${P.text}`, kind: "death", seq };
    case "vote":
      return { text: `投票：${actor}号 → ${P.target}号`, kind: "public", seq };
    case "pk_vote":
      return { text: `PK投票：${actor}号 → ${P.target}号`, kind: "public", seq };
    case "election_vote":
      return { text: `警长票：${actor}号 → ${P.target}号`, kind: "public", seq };
    case "election_pk_vote":
      return { text: `警长PK票：${actor}号 → ${P.target}号`, kind: "public", seq };
    case "wolf_chat":
      return { text: `【狼队】${actor}号：${P.text || ""}`, kind: "wolf", seq };
    case "wolf_vote":
      return { text: `${actor}号狼选择击杀 ${P.target}号`, kind: "wolf", seq };
    case "wolf_kill_result":
      return P.target
        ? { text: `狼人今夜选择击杀 ${P.target}号`, kind: "wolf", seq }
        : { text: "狼人本夜空刀", kind: "wolf", seq };
    case "guard_action":
      return { text: `你守护了 ${P.target}号`, kind: "private", seq };
    case "seer_result":
      return P.target === null || P.target === undefined
        ? { text: "你选择不查验", kind: "private", seq }
        : { text: `你查验了 ${P.target}号：${P.result === "wolf" ? "狼人" : "好人"}`, kind: "private", seq };
    case "witch_info":
      return P.victim === null || P.victim === undefined
        ? { text: "你得知今夜无人被狼人袭击", kind: "private", seq }
        : { text: `你得知今夜被袭击的是 ${P.victim}号`, kind: "private", seq };
    case "witch_action":
      if (P.action === "save") return { text: `你使用了解药（救 ${P.target}号）`, kind: "private", seq };
      if (P.action === "poison") return { text: `你使用了毒药（毒 ${P.target}号）`, kind: "private", seq };
      return { text: "你选择不用药", kind: "private", seq };
    case "night_result":
      return P.peaceful
        ? { text: "🌙 昨夜平安", kind: "death", seq }
        : { text: `🌙 昨夜出局：${(P.deaths || []).map((d: any) => `${d.seat}号${DEATH_MODES[d.mode] || "死亡"}`).join("、")}`, kind: "death", seq };
    case "hunter_shot":
      return P.target
        ? { text: `🔫 ${actor}号猎人开枪带走 ${P.target}号`, kind: "death", seq }
        : { text: `${actor}号猎人选择不开枪`, kind: "public", seq };
    case "lynch_result":
      return P.seat
        ? { text: `⚖️ 放逐：${P.seat}号被放逐`, kind: "death", seq }
        : { text: "⚖️ 放逐投票：无人被放逐", kind: "public", seq };
    case "wolf_explode":
      return { text: `💥 ${actor}号狼人自爆！`, kind: "death", seq };
    case "sheriff_apply":
      return { text: `${actor}号上警`, kind: "public", seq };
    case "sheriff_withdraw":
      return { text: `${actor}号退水`, kind: "public", seq };
    case "sheriff_pass":
      return { text: `${actor}号不上警`, kind: "public", seq };
    case "sheriff_elected":
      return { text: `🎖️ ${P.seat}号当选警长`, kind: "system", seq };
    case "sheriff_transfer":
      return { text: `🎖️ 警长将警徽移交给 ${P.target}号`, kind: "system", seq };
    case "sheriff_destroy":
      return { text: "🎖️ 警长撕毁警徽", kind: "system", seq };
    case "seat_control":
      return { text: `${actor}号转为${P.controller_type === "human" ? "人类接管" : "AI托管"}`, kind: "system", seq };
    case "game_over": {
      const winner = P.winner === "good" ? "好人阵营" : "狼人阵营";
      return { text: `🏁 游戏结束：${winner}获胜（${P.reason || ""}）`, kind: "system", seq };
    }
    default:
      return null;
  }
}

export { DEATH_MODES };
