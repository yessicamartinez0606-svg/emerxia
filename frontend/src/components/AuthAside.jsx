import { Logo } from './Logo.jsx'
import Heartbeat from './Heartbeat.jsx'
import ambulancePhoto from '../assets/ambulance.jpg'

export default function AuthAside({ tagline = 'Conectando profesionales,\nsalvando vidas' }) {
  return (
    <aside className="login-brand">
      <img className="brand-photo" src={ambulancePhoto} alt="" />
      <div className="brand-tint" aria-hidden="true" />
      <Heartbeat />
      <div className="brand-lockup">
        <Logo size={46} />
        <p>{tagline.split('\n').map((line, i) => (
          <span key={i}>{line}{i < tagline.split('\n').length - 1 && <br />}</span>
        ))}</p>
      </div>
    </aside>
  )
}
