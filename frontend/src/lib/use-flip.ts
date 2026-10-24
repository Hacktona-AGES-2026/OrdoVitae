import { useLayoutEffect, useRef } from "react"

/**
 * Animação FLIP: quando a ordem dos filhos muda (ex.: a fila de um dia para o outro), cada elemento
 * desliza da posição antiga para a nova em vez de "pular". Os filhos precisam de `data-flip="<chave>"`.
 * Elementos novos entram com fade. Respeita prefers-reduced-motion.
 */
export function useFlip<T extends HTMLElement>(dependencia: unknown) {
  const ref = useRef<T>(null)
  const anteriores = useRef(new Map<string, DOMRect>())

  useLayoutEffect(() => {
    const raiz = ref.current
    if (!raiz) return
    const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const atuais = new Map<string, DOMRect>()
    const elementos = raiz.querySelectorAll<HTMLElement>("[data-flip]")

    elementos.forEach((el) => atuais.set(el.dataset.flip!, el.getBoundingClientRect()))
    if (!reduzir && anteriores.current.size > 0) {
      elementos.forEach((el) => {
        const antes = anteriores.current.get(el.dataset.flip!)
        const agora = atuais.get(el.dataset.flip!)!
        if (!antes) {
          el.animate([{ opacity: 0, transform: "scale(0.98)" }, { opacity: 1, transform: "none" }], {
            duration: 350,
            easing: "ease-out",
          })
          return
        }
        const dx = antes.left - agora.left
        const dy = antes.top - agora.top
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return
        el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], {
          duration: 600,
          easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
        })
      })
    }
    anteriores.current = atuais
  }, [dependencia])

  return ref
}
