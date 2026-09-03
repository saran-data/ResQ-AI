/**
 * ResQAI - Core TypeScript Type Definitions
 * Shared types used across the entire frontend application.
 */

// -------------------------------------------------------
// Enumerations
// -------------------------------------------------------

export enum UserRole {
  SUPER_ADMIN = "super_admin",
  ADMIN = "admin",
  RESTAURANT_OWNER = "restaurant_owner",
  RESTAURANT_STAFF = "restaurant_staff",
  NGO_MANAGER = "ngo_manager",
  NGO_STAFF = "ngo_staff",
  VOLUNTEER = "volunteer",
  DRIVER = "driver",
}

export enum DonationStatus {
  DRAFT = "draft",
  PENDING_ANALYSIS = "pending_analysis",
  ANALYZED = "analyzed",
  SAFETY_CHECK = "safety_check",
  MATCHING = "matching",
  MATCHED = "matched",
  PICKUP_SCHEDULED = "pickup_scheduled",
  PICKED_UP = "picked_up",
  IN_TRANSIT = "in_transit",
  DELIVERED = "delivered",
  CONFIRMED = "confirmed",
  CANCELLED = "cancelled",
  REJECTED = "rejected",
  EXPIRED = "expired",
}

export enum FoodCategory {
  COOKED_MEAL = "cooked_meal",
  RAW_PRODUCE = "raw_produce",
  BAKERY = "bakery",
  DAIRY = "dairy",
  BEVERAGES = "beverages",
  PACKAGED = "packaged",
  SNACKS = "snacks",
  DESSERTS = "desserts",
}

export enum AgentType {
  FOOD_ANALYSIS = "food_analysis",
  NGO_MATCHING = "ngo_matching",
  ROUTE_OPTIMIZATION = "route_optimization",
  FOOD_SAFETY = "food_safety",
  DEMAND_PREDICTION = "demand_prediction",
  NOTIFICATION = "notification",
  VOLUNTEER = "volunteer",
  ANALYTICS = "analytics",
  FRAUD_DETECTION = "fraud_detection",
  ADMIN_ASSISTANT = "admin_assistant",
}

export enum AgentStatus {
  IDLE = "idle",
  RUNNING = "running",
  SUCCESS = "success",
  FAILED = "failed",
  RETRYING = "retrying",
}

export enum NotificationType {
  DONATION_CREATED = "donation_created",
  DONATION_MATCHED = "donation_matched",
  PICKUP_SCHEDULED = "pickup_scheduled",
  DELIVERY_STARTED = "delivery_started",
  DELIVERY_COMPLETED = "delivery_completed",
  OTP_GENERATED = "otp_generated",
  SAFETY_REJECTED = "safety_rejected",
  FRAUD_DETECTED = "fraud_detected",
  SYSTEM_ALERT = "system_alert",
}

// -------------------------------------------------------
// Core Entities
// -------------------------------------------------------

export interface User {
  id: string;
  email: string;
  name: string;
  phone?: string;
  avatar?: string;
  role: UserRole;
  isActive: boolean;
  isVerified: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Restaurant {
  id: string;
  name: string;
  type: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  latitude: number;
  longitude: number;
  phone: string;
  email: string;
  fssaiLicense: string;
  isVerified: boolean;
  isActive: boolean;
  rating: number;
  totalDonations: number;
  totalMealsSaved: number;
  carbonSaved: number;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
}

export interface NGO {
  id: string;
  name: string;
  type: string;
  registrationNumber: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  latitude: number;
  longitude: number;
  phone: string;
  email: string;
  capacityPerDay: number;
  currentCapacity: number;
  storageAvailable: boolean;
  refrigerationAvailable: boolean;
  foodPreferences: string[];
  dietaryRestrictions: string[];
  serviceHours: string;
  isVerified: boolean;
  isActive: boolean;
  managerId: string;
  totalReceived: number;
  beneficiariesCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Volunteer {
  id: string;
  userId: string;
  name: string;
  phone: string;
  email: string;
  city: string;
  latitude: number;
  longitude: number;
  vehicleType?: string;
  vehicleNumber?: string;
  isAvailable: boolean;
  currentDeliveries: number;
  maxDeliveries: number;
  rating: number;
  totalDeliveries: number;
  createdAt: string;
}

export interface FoodItem {
  id: string;
  donationId: string;
  name: string;
  category: FoodCategory;
  quantity: number;
  unit: string;
  estimatedServings: number;
  preparationTime: string;
  expiryTime: string;
  storageTemperature: number;
  isVegetarian: boolean;
  isVegan: boolean;
  allergens: string[];
  imageUrl: string;
  aiAnalysis?: FoodAIAnalysis;
}

export interface Donation {
  id: string;
  restaurantId: string;
  restaurant?: Restaurant;
  status: DonationStatus;
  foodItems: FoodItem[];
  totalServings: number;
  pickupAddress: string;
  pickupLatitude: number;
  pickupLongitude: number;
  pickupWindow: string;
  specialInstructions?: string;
  matchedNgoId?: string;
  matchedNgo?: NGO;
  volunteerId?: string;
  volunteer?: Volunteer;
  deliveryId?: string;
  otp?: string;
  qrCode?: string;
  aiDecisions: AIDecision[];
  createdAt: string;
  updatedAt: string;
}

export interface Delivery {
  id: string;
  donationId: string;
  volunteerId: string;
  ngoId: string;
  status: string;
  routeId?: string;
  currentLatitude?: number;
  currentLongitude?: number;
  estimatedArrival?: string;
  actualPickupTime?: string;
  actualDeliveryTime?: string;
  distanceKm: number;
  durationMinutes: number;
  createdAt: string;
}

export interface Route {
  id: string;
  deliveryId: string;
  polyline: string;
  waypoints: Waypoint[];
  totalDistanceKm: number;
  totalDurationMinutes: number;
  algorithm: string;
  trafficAware: boolean;
  createdAt: string;
}

export interface Waypoint {
  latitude: number;
  longitude: number;
  label: string;
  estimatedArrival?: string;
}

// -------------------------------------------------------
// AI Types
// -------------------------------------------------------

export interface FoodAIAnalysis {
  confidenceScore: number;
  estimatedServings: number;
  freshnessScore: number;
  estimatedExpiryHours: number;
  classification: string;
  detectedItems: string[];
  safetyScore: number;
  recommendation: string;
  modelUsed: string;
  analysisTime: number;
}

export interface AIDecision {
  id: string;
  donationId: string;
  agentType: AgentType;
  status: AgentStatus;
  inputData: Record<string, unknown>;
  outputData: Record<string, unknown>;
  confidenceScore: number;
  reasoning: string;
  modelUsed: string;
  latencyMs: number;
  retryCount: number;
  createdAt: string;
}

export interface AgentState {
  agentType: AgentType;
  status: AgentStatus;
  currentTask?: string;
  lastRun?: string;
  successRate: number;
  averageLatencyMs: number;
}

// -------------------------------------------------------
// Analytics Types
// -------------------------------------------------------

export interface DashboardKPIs {
  totalDonations: number;
  totalMealsSaved: number;
  carbonSavedKg: number;
  activeRestaurants: number;
  activeNGOs: number;
  activeVolunteers: number;
  avgDeliveryTimeMinutes: number;
  successRate: number;
  todayDonations: number;
  weeklyGrowth: number;
}

export interface TimeSeriesData {
  date: string;
  value: number;
  label?: string;
}

export interface HeatmapData {
  latitude: number;
  longitude: number;
  weight: number;
}

// -------------------------------------------------------
// API Response Types
// -------------------------------------------------------

export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  message?: string;
  error?: ApiError;
  pagination?: Pagination;
  requestId?: string;
}

export interface ApiError {
  code: number;
  message: string;
  type: string;
  details?: unknown;
}

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: Pagination;
}

// -------------------------------------------------------
// WebSocket Types
// -------------------------------------------------------

export interface WSMessage<T = unknown> {
  event: string;
  data: T;
  timestamp: string;
  requestId?: string;
}

export interface TrackingUpdate {
  deliveryId: string;
  latitude: number;
  longitude: number;
  speed?: number;
  heading?: number;
  timestamp: string;
}

export interface NotificationPayload {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  data?: Record<string, unknown>;
  read: boolean;
  createdAt: string;
}

// -------------------------------------------------------
// Form Types
// -------------------------------------------------------

export interface DonationFormData {
  foodItems: {
    name: string;
    category: FoodCategory;
    quantity: number;
    unit: string;
    isVegetarian: boolean;
    isVegan: boolean;
    images: File[];
  }[];
  pickupAddress: string;
  pickupLatitude: number;
  pickupLongitude: number;
  pickupWindowStart: string;
  pickupWindowEnd: string;
  specialInstructions?: string;
}

export interface LoginFormData {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RegisterFormData {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  phone: string;
  role: UserRole;
  organizationName?: string;
}
