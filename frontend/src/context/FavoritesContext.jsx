import React, { createContext, useContext, useState, useEffect } from 'react';

const FavoritesContext = createContext();

export const useFavorites = () => {
  const context = useContext(FavoritesContext);
  if (!context) {
    throw new Error('useFavorites must be used within a FavoritesProvider');
  }
  return context;
};

export const FavoritesProvider = ({ children }) => {
  const [favorites, setFavorites] = useState([]);

  useEffect(() => {
    const saved = localStorage.getItem('exosignal_favorites');
    if (saved) {
      try {
        setFavorites(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse favorites:', e);
      }
    }
  }, []);

  const addFavorite = (planet) => {
    setFavorites((prev) => {
      const exists = prev.find((p) => p.planet_name === planet.planet_name);
      if (exists) return prev;
      const newFavorites = [...prev, planet];
      localStorage.setItem('exosignal_favorites', JSON.stringify(newFavorites));
      return newFavorites;
    });
  };

  const removeFavorite = (planetName) => {
    setFavorites((prev) => {
      const newFavorites = prev.filter((p) => p.planet_name !== planetName);
      localStorage.setItem('exosignal_favorites', JSON.stringify(newFavorites));
      return newFavorites;
    });
  };

  const isFavorite = (planetName) => {
    return favorites.some((p) => p.planet_name === planetName);
  };

  const toggleFavorite = (planet) => {
    if (isFavorite(planet.planet_name)) {
      removeFavorite(planet.planet_name);
    } else {
      addFavorite(planet);
    }
  };

  return (
    <FavoritesContext.Provider
      value={{ favorites, addFavorite, removeFavorite, isFavorite, toggleFavorite }}
    >
      {children}
    </FavoritesContext.Provider>
  );
};
