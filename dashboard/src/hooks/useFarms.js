/**
 * useFarms.js
 * React hook managing the farm list and active farm selection.
 */

import { useState, useCallback } from 'react'
import {
  loadFarms, loadActiveFarmId, saveActiveFarmId,
  addFarm, updateFarm, deleteFarm,
} from '../services/farmStore'

// Default farm used when nothing is saved yet
const DEFAULT_FARM = {
  id:       'default',
  name:     'Default Farm',
  location: 'Kolkata, West Bengal',
  lat:      22.5726,
  lon:      88.3639,
}

export function useFarms() {
  const [farms, setFarms]           = useState(() => {
    const saved = loadFarms()
    return saved.length > 0 ? saved : [DEFAULT_FARM]
  })

  const [activeFarmId, setActiveId] = useState(() => {
    const savedId = loadActiveFarmId()
    const saved   = loadFarms()
    if (saved.length === 0) return 'default'
    return savedId ?? saved[0].id
  })

  const activeFarm = farms.find(f => f.id === activeFarmId) ?? farms[0] ?? DEFAULT_FARM

  const selectFarm = useCallback((id) => {
    setActiveId(id)
    saveActiveFarmId(id)
  }, [])

  const createFarm = useCallback((data) => {
    const { farm, farms: updated } = addFarm(data)
    setFarms(updated)
    setActiveId(farm.id)
    saveActiveFarmId(farm.id)
    return farm
  }, [])

  const editFarm = useCallback((id, patch) => {
    const updated = updateFarm(id, patch)
    setFarms(updated)
  }, [])

  const removeFarm = useCallback((id) => {
    const updated = deleteFarm(id)
    // If only the default placeholder is left, restore it
    const next = updated.length > 0 ? updated : [DEFAULT_FARM]
    setFarms(next)
    if (activeFarmId === id) {
      const newId = next[0]?.id ?? 'default'
      setActiveId(newId)
      saveActiveFarmId(newId)
    }
  }, [activeFarmId])

  return { farms, activeFarm, activeFarmId, selectFarm, createFarm, editFarm, removeFarm }
}
