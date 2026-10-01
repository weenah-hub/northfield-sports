/*
  App shell
  =========
  Routes and layout for the storefront.
*/

import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { CartProvider } from './CartContext'
import Header from './components/Header'
import Footer from './components/Footer'
import Shop from './pages/Shop'
import Checkout from './pages/Checkout'
import OrderConfirmation from './pages/OrderConfirmation'
import Orders from './pages/Orders'
import SignInCallback from './pages/SignInCallback'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <div className="app-shell">
            <Header />
            <main className="app-main">
              <Routes>
                <Route path="/" element={<Shop />} />
                <Route path="/checkout" element={<Checkout />} />
                <Route path="/order/:orderId" element={<OrderConfirmation />} />
                <Route path="/orders" element={<Orders />} />
                <Route path="/signin-callback" element={<SignInCallback />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
